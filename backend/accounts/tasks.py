"""Delivery of account mail: the ledger owner, mirroring ``push.tasks``.

The request path never sends mail. It writes an :class:`AccountEmail` row and
enqueues this task; the beat schedule re-scans PENDING rows, so a broker outage
delays a reset link instead of losing it.

The link secret is minted here rather than at request time, so a usable link
never exists at rest and its lifetime starts when the mail actually goes out.
"""

from datetime import timedelta
import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from common.metrics import increment
from common.security import create_link_token, hash_secret

from .mail import account_link, mail_is_configured, render, send_account_email
from .models import AccountEmail, AccountToken

logger = logging.getLogger("anicast.accounts")

MAX_ATTEMPTS = 3
# A reset link that leaves hours after it was asked for is worse than none: the
# person has already given up, and the mail only teaches them that AniCast sends
# late security mail. Rows older than this are closed as EXPIRED and the user is
# free to ask again.
STALE_AFTER = timedelta(hours=1)

# Which page consumes each link, and whether the link carries a secret at all.
# The password-changed notice points at the recovery page with no token: it is a
# warning, not an authorisation, so it must not embed a credential.
LINK_PATHS: dict[str, str] = {
    AccountEmail.Kind.PASSWORD_RESET: "/reset-password",
    AccountEmail.Kind.EMAIL_VERIFICATION: "/verify-email",
}
TOKEN_PURPOSES: dict[str, str] = {
    AccountEmail.Kind.PASSWORD_RESET: AccountToken.Purpose.PASSWORD_RESET,
    AccountEmail.Kind.EMAIL_VERIFICATION: AccountToken.Purpose.EMAIL_VERIFICATION,
}


def link_ttl_hours() -> int:
    return max(1, int(settings.ACCOUNT_LINK_TTL_SECONDS) // 3600)


def enqueue_account_email(user, kind: str, to_address: str) -> AccountEmail:
    """Record one outbound message; the ledger guarantees it is attempted.

    Dispatch is best-effort on purpose so a missing broker never fails the
    request the person is waiting on — the beat task picks the row up anyway.
    """
    record = AccountEmail.objects.create(user=user, kind=kind, to_address=to_address)
    try:
        dispatch_account_emails.delay()
    except Exception:
        logger.warning(
            "account email deferred to beat",
            extra={"event": "account_email_deferred", "kind": kind},
            exc_info=True,
        )
    return record


def issue_token(record: AccountEmail) -> str:
    """Mint the single-use secret for this message and store only its hash.

    Any earlier unconsumed token for the same purpose is dropped first: two live
    reset links for one account widen the window for no benefit, and the person
    is looking at the newest mail anyway.
    """
    purpose = TOKEN_PURPOSES[record.kind]
    AccountToken.objects.filter(user=record.user, purpose=purpose, consumed_at__isnull=True).delete()
    raw_token = create_link_token()
    record.token = AccountToken.objects.create(
        user=record.user,
        purpose=purpose,
        token_hash=hash_secret(raw_token),
        email=record.to_address,
        expires_at=timezone.now() + timedelta(seconds=int(settings.ACCOUNT_LINK_TTL_SECONDS)),
    )
    return raw_token


@shared_task
def dispatch_account_emails():
    if not mail_is_configured():
        # Nothing is lost: rows stay PENDING until mail is configured, and the
        # endpoints already refuse to promise delivery in this state.
        return {"sent": 0, "failed": 0, "skipped": "mail_not_configured"}
    now = timezone.now()
    stale = AccountEmail.objects.filter(
        status=AccountEmail.Status.PENDING, created_at__lt=now - STALE_AFTER,
    ).update(status=AccountEmail.Status.EXPIRED, updated_at=now)
    pending = AccountEmail.objects.filter(
        status__in=[AccountEmail.Status.PENDING, AccountEmail.Status.FAILED],
        attempts__lt=MAX_ATTEMPTS,
        created_at__gte=now - STALE_AFTER,
    ).select_related("user").order_by("created_at", "id")
    sent = failed = 0
    for record in pending:
        raw_token = issue_token(record) if record.kind in TOKEN_PURPOSES else ""
        path = LINK_PATHS.get(record.kind, "/forgot-password")
        url = account_link(path, raw_token) if raw_token else f"{settings.ANICAST_SITE_URL}{path}"
        subject, text, html = render(
            record.kind, record.user.preferred_language, url, link_ttl_hours(),
        )
        record.attempts += 1
        try:
            send_account_email(record.to_address, subject, text, html)
        except SoftTimeLimitExceeded:
            # A soft timeout must abort the batch, not be recorded as this
            # recipient's failure. The row keeps its issued token and is retried.
            record.status = AccountEmail.Status.PENDING
            record.save(update_fields=["attempts", "status", "token", "updated_at"])
            raise
        except Exception as exc:
            record.status = AccountEmail.Status.FAILED
            record.error = f"{type(exc).__name__}: {exc}"[:500]
            failed += 1
            increment("account_emails", "failed")
            logger.warning("account email failed", extra={
                "event": "account_email_failed", "kind": record.kind,
                "exception_type": type(exc).__name__, "attempts": record.attempts,
            })
        else:
            record.status = AccountEmail.Status.SENT
            record.sent_at = timezone.now()
            record.error = ""
            sent += 1
            increment("account_emails", "sent")
        record.save(update_fields=["status", "attempts", "error", "sent_at", "token", "updated_at"])
    logger.info("account email batch completed", extra={
        "event": "account_email_batch_completed", "sent": sent, "failed": failed, "expired": stale,
    })
    return {"sent": sent, "failed": failed, "expired": stale}
