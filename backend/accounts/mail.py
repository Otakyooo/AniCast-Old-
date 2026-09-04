"""Outbound account mail: the one place that talks to the SMTP server.

Unlike Telegram, SMTP egress from MainServer works — verified 2026-09-04 from
the host and from the backend container against Gmail, Yandex, Resend, Postmark
and SES (587 and 465 connect, STARTTLS completes). So this needs no relay: it is
Django's own SMTP backend with credentials from the environment.

Composition lives here and delivery lives in :mod:`accounts.tasks`, mirroring
``push.telegram`` / ``push.tasks``: a bounded send function that raises, and a
caller that owns the ledger and the retries.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils.html import escape

from .models import AccountEmail

SITE_URL = getattr(settings, "ANICAST_SITE_URL", "https://anicast.online")


def mail_is_configured() -> bool:
    """Whether a delivery attempt can reach a server at all.

    Only the SMTP backend needs a host; the console and locmem backends used in
    development and tests are configured by definition. Endpoints check this and
    answer 503 with a reason rather than accepting a request whose whole purpose
    is an email that will never be sent.
    """
    backend = str(getattr(settings, "EMAIL_BACKEND", ""))
    if backend.endswith("smtp.EmailBackend"):
        return bool(getattr(settings, "EMAIL_HOST", ""))
    return bool(backend)


def account_link(path: str, token: str) -> str:
    return f"{SITE_URL}{path}?token={token}"


# Every message is a subject plus paragraphs, where ``{url}`` is a paragraph of
# its own. The link is always rendered as its own visible URL: a label that
# differs from its target is what both a phishing filter and a careful reader
# flag, and the address bar is the only thing proving this mail is from AniCast.
BODIES: dict[str, dict[str, tuple[str, tuple[str, ...]]]] = {
    AccountEmail.Kind.PASSWORD_RESET: {
        "ru": (
            "Сброс пароля AniCast",
            (
                "Кто-то запросил сброс пароля для этого адреса на AniCast.",
                "Чтобы задать новый пароль, откройте ссылку:",
                "{url}",
                "Ссылка действует {hours} ч и работает один раз. Если это были не вы, "
                "ничего делать не нужно: пароль останется прежним.",
            ),
        ),
        "en": (
            "Reset your AniCast password",
            (
                "Someone requested a password reset for this address on AniCast.",
                "To set a new password, open this link:",
                "{url}",
                "The link is valid for {hours} h and works once. If this was not you, "
                "no action is needed — your password stays as it is.",
            ),
        ),
    },
    AccountEmail.Kind.EMAIL_VERIFICATION: {
        "ru": (
            "Подтверждение адреса на AniCast",
            (
                "Подтвердите, что этот адрес принадлежит вам.",
                "Откройте ссылку:",
                "{url}",
                "Ссылка действует {hours} ч. Без подтверждения аккаунт продолжит "
                "работать, но восстановить пароль по этому адресу не получится.",
            ),
        ),
        "en": (
            "Confirm your AniCast address",
            (
                "Confirm that this address belongs to you.",
                "Open this link:",
                "{url}",
                "The link is valid for {hours} h. Without confirmation the account "
                "keeps working, but password recovery to this address will not be "
                "possible.",
            ),
        ),
    },
    AccountEmail.Kind.PASSWORD_CHANGED: {
        "ru": (
            "Пароль AniCast изменён",
            (
                "Пароль вашего аккаунта AniCast был изменён, а остальные сессии завершены.",
                "Если это сделали не вы, немедленно запросите сброс пароля:",
                "{url}",
            ),
        ),
        "en": (
            "Your AniCast password changed",
            (
                "The password for your AniCast account was changed and all other "
                "sessions were signed out.",
                "If this was not you, request a password reset immediately:",
                "{url}",
            ),
        ),
    },
}


def render(kind: str, language: str, url: str, ttl_hours: int) -> tuple[str, str, str]:
    """Return ``(subject, text, html)`` for one message."""
    variants = BODIES[kind]
    subject, paragraphs = variants.get(language) or variants["ru"]
    filled = [paragraph.format(url=url, hours=ttl_hours) for paragraph in paragraphs]
    text = "\n\n".join(filled)
    safe_url = escape(url)
    blocks = []
    for paragraph, template in zip(filled, paragraphs, strict=True):
        body = f'<a href="{safe_url}">{safe_url}</a>' if template == "{url}" else escape(paragraph)
        blocks.append(f'<p style="margin:0 0 14px">{body}</p>')
    html = (
        '<div style="font:15px/1.6 system-ui,sans-serif;color:#111">'
        '<p style="margin:0 0 18px;font-weight:700">AniCast</p>'
        f"{''.join(blocks)}"
        "</div>"
    )
    return subject, text, html


def send_account_email(to_address: str, subject: str, text: str, html: str) -> None:
    """Deliver one message, raising on any failure.

    ``fail_silently`` stays off deliberately: the caller records the outcome in
    the ledger and retries, which is impossible if the backend swallows errors.
    """
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_address],
        connection=get_connection(fail_silently=False),
    )
    message.attach_alternative(html, "text/html")
    if not message.send():
        raise RuntimeError("SMTP backend accepted no recipients")
