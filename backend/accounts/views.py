from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login, logout, password_validation, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle

from common.security import constant_time_equals, create_link_token, hash_secret, valid_link_token
from common.throttling import LiveRatesMixin

from .mail import mail_is_configured
from .models import AccountEmail, AccountToken, ExternalIdentity, TelegramLoginChallenge, User
from .serializers import (
    EmailRequestSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PublicProfileUpdateSerializer,
    RegisterSerializer,
    UserPreferencesSerializer,
    UserSerializer,
)
from .tasks import enqueue_account_email


class AuthRateThrottle(LiveRatesMixin, SimpleRateThrottle):
    """IP-scoped auth throttle that also applies to authenticated callers.

    DRF's AnonRateThrottle skips logged-in requests entirely, which let a
    single throwaway session brute-force login at unlimited rate.
    """

    scope = "auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class RegisterRateThrottle(AuthRateThrottle):
    """Tighter bucket for registration, because it answers a question login does not.

    Login is deliberately generic ("wrong email or password"), so it reveals
    nothing about which addresses exist. Registration must tell a returning user
    that their account already exists, and that makes it an enumeration oracle.

    Sharing login's 10/min budget allowed ~14k probes a day from one address. A
    genuine person registers once, so an hourly bucket is invisible to them while
    cutting enumeration throughput by roughly thirty times. Verification by mail
    does not remove this oracle either: the address must still be rejected as
    taken, because silently attaching a second registration to someone else's
    account would be worse than the disclosure.
    """

    scope = "register"


class MailRateThrottle(LiveRatesMixin, SimpleRateThrottle):
    """Per-address bucket for endpoints that put mail in someone's inbox.

    The IP bucket alone is the wrong axis here: the cost of abuse falls on the
    mailbox owner, and a botnet has many addresses while the victim has one. So
    these requests are counted per target address as well, and the response is
    identical either way — a throttled request must not become the signal that
    the address exists.

    The key is the SHA-256 of the address, not the address itself: throttle keys
    live in the Redis instance shared with the cache and this endpoint is open to
    anyone, so raw keys would let anything that can read Redis enumerate which
    addresses were tried.
    """

    scope = "account_mail"

    def get_cache_key(self, request, view):
        target = str(request.data.get("email", "")).strip().lower()
        if not target:
            # Authenticated mail endpoints carry no address in the body; the
            # target is the account's own.
            target = (getattr(request.user, "email", "") or "").lower()
        if not target:
            return None
        return self.cache_format % {"scope": self.scope, "ident": hash_secret(target)}


def enforce_csrf(request):
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


def mail_unavailable_response():
    return Response(
        {"detail": "Отправка писем пока не настроена. Обратитесь в поддержку."}, status=503,
    )


def consume_token(raw_token: str, purpose: str):
    """Return the row for a valid unconsumed link, or ``None``.

    Marking it consumed happens in the same transaction as the state change it
    authorises, so a link is never spent by a request that then fails.
    """
    if not valid_link_token(raw_token):
        return None
    return AccountToken.objects.select_for_update().select_related("user").filter(
        token_hash=hash_secret(raw_token),
        purpose=purpose,
        consumed_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegisterRateThrottle])
def register(request):
    enforce_csrf(request)
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        user = serializer.save()
    except IntegrityError:
        return Response({"email": ["Аккаунт с таким email уже существует."]}, status=400)
    login(request, user)
    # Verification is offered, not enforced: the account works immediately, and
    # the address only needs proving before it is trusted for recovery. A mail
    # outage must not block registration, so a failure here is invisible.
    if mail_is_configured():
        enqueue_account_email(user, AccountEmail.Kind.EMAIL_VERIFICATION, user.email)
    return Response(UserSerializer(user).data, status=201)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def sign_in(request):
    enforce_csrf(request)
    serializer = LoginSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sign_out(request):
    enforce_csrf(request)
    logout(request)
    return Response(status=204)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user(request):
    return Response(UserSerializer(request.user).data)


def delete_user_sessions(user, keep: str | None = None) -> int:
    """Delete this user's session rows, optionally sparing one key.

    Sessions are opaque: the payload holds the user id, so the only way to find
    them is to walk unexpired rows and decode each. That cost is acceptable
    because it runs on explicit, throttled actions.

    For a password change this is not what logs the other devices out — Django
    stores a password-derived hash in the session and ``get_user`` rejects a
    mismatch, so they are already unauthenticated. Deleting the rows is what
    makes the reported count truthful and drops the leftover session data. For
    :func:`revoke_sessions`, where the password does not change, deletion is the
    only mechanism there is — and its absence is what made a stolen 30-day
    rolling cookie irrevocable.
    """
    from django.contrib.sessions.models import Session

    user_id = str(user.pk)
    revoked = 0
    rows = Session.objects.filter(expire_date__gte=timezone.now()).only("session_key", "session_data")
    for session in rows.iterator(chunk_size=500):
        if keep is not None and session.session_key == keep:
            continue
        try:
            data = session.get_decoded()
        except Exception:
            # A row we cannot decode cannot be attributed, so leave it alone: it
            # expires by itself, and deleting it could sign out a stranger.
            continue
        if data.get("_auth_user_id") == user_id:
            session.delete()
            revoked += 1
    return revoked


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthRateThrottle])
def revoke_sessions(request):
    """Sign out every other device without changing the password.

    A 30-day rolling cookie is convenient and, without this, irrevocable: the
    only remedy for a stolen session was to change the password or wait a month.
    """
    enforce_csrf(request)
    return Response({"revoked": delete_user_sessions(request.user, keep=request.session.session_key)})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle, MailRateThrottle])
def password_reset_request(request):
    """Ask for a reset link. The answer never depends on the address.

    Every branch below returns the same 202: unknown address, disabled account,
    unverified address. Otherwise this endpoint would become the enumeration
    oracle that login carefully avoids being.
    """
    enforce_csrf(request)
    serializer = EmailRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if not mail_is_configured():
        return mail_unavailable_response()
    email = serializer.validated_data["email"]
    accepted = Response({"detail": "Если такой аккаунт есть, письмо со ссылкой отправлено."}, status=202)
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None or not user.email:
        return accepted
    # An unverified address is not proven to belong to this account, so mailing a
    # reset link to it would let whoever typo'd it during registration — or
    # deliberately claimed it — seize the account. Verification comes first, and
    # the response stays identical either way.
    kind = (
        AccountEmail.Kind.PASSWORD_RESET
        if user.email_is_verified
        else AccountEmail.Kind.EMAIL_VERIFICATION
    )
    enqueue_account_email(user, kind, user.email)
    return accepted


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def password_reset_confirm(request):
    enforce_csrf(request)
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    password = serializer.validated_data["password"]
    invalid = Response({"detail": "Ссылка недействительна или устарела. Запросите новую."}, status=400)
    with transaction.atomic():
        token = consume_token(serializer.validated_data["token"], AccountToken.Purpose.PASSWORD_RESET)
        if token is None or not token.user.is_active:
            return invalid
        user = token.user
        try:
            password_validation.validate_password(password, user)
        except DjangoValidationError as error:
            return Response({"password": list(error.messages)}, status=400)
        user.set_password(password)
        updated = ["password"]
        # Opening the link proves control of the mailbox, which is exactly the
        # evidence verification asks for, so a reset also repairs an account whose
        # address was never confirmed.
        if not user.email_is_verified and user.email and user.email.lower() == token.email.lower():
            user.email_verified_at = timezone.now()
            updated.append("email_verified_at")
        user.save(update_fields=updated)
        token.consumed_at = timezone.now()
        token.save(update_fields=["consumed_at"])
        AccountToken.objects.filter(
            user=user, purpose=AccountToken.Purpose.PASSWORD_RESET, consumed_at__isnull=True,
        ).delete()
    # A reset is the remedy for a compromised account, so it ends every existing
    # session — including the attacker's — and not just the password.
    delete_user_sessions(user)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthRateThrottle])
def password_change(request):
    enforce_csrf(request)
    serializer = PasswordChangeSerializer(data=request.data, context={"user": request.user})
    serializer.is_valid(raise_exception=True)
    user = request.user
    user.set_password(serializer.validated_data["password"])
    user.save(update_fields=["password"])
    revoked = delete_user_sessions(user, keep=request.session.session_key)
    # Keep this browser signed in: the session hash derives from the password, so
    # without this the person who just changed it is logged out as well.
    update_session_auth_hash(request, user)
    # Any live reset link predates the new password; leaving it usable would let
    # an older mailbox capture undo the change.
    AccountToken.objects.filter(
        user=user, purpose=AccountToken.Purpose.PASSWORD_RESET, consumed_at__isnull=True,
    ).delete()
    if user.email and user.email_is_verified and mail_is_configured():
        enqueue_account_email(user, AccountEmail.Kind.PASSWORD_CHANGED, user.email)
    return Response({"revoked": revoked})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthRateThrottle, MailRateThrottle])
def email_verification_request(request):
    enforce_csrf(request)
    user = request.user
    if not user.email:
        return Response({"detail": "К аккаунту не привязан адрес."}, status=400)
    if user.email_is_verified:
        return Response({"detail": "Адрес уже подтверждён."}, status=409)
    if not mail_is_configured():
        return mail_unavailable_response()
    enqueue_account_email(user, AccountEmail.Kind.EMAIL_VERIFICATION, user.email)
    return Response({"detail": "Письмо с подтверждением отправлено."}, status=202)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def email_verification_confirm(request):
    """Confirm an address. Deliberately open to anonymous callers.

    The link arrives by mail and is often opened in a different browser than the
    one that registered, so requiring a session here would strand people holding
    a valid link. The token is the evidence: single-use and short-lived.
    """
    enforce_csrf(request)
    with transaction.atomic():
        token = consume_token(request.data.get("token"), AccountToken.Purpose.EMAIL_VERIFICATION)
        if token is None:
            return Response({"detail": "Ссылка недействительна или устарела. Запросите новую."}, status=400)
        user = token.user
        # What is proven is the address the link was sent to, not whatever the
        # account holds now: if it changed since, this link says nothing about it.
        # The token is left unspent — it still proves that address, so restoring
        # it makes the link work again, and it can never confirm a different one.
        if not user.email or user.email.lower() != token.email.lower():
            return Response({"detail": "Адрес аккаунта изменился. Запросите новое письмо."}, status=409)
        token.consumed_at = timezone.now()
        token.save(update_fields=["consumed_at"])
        if not user.email_is_verified:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
    return Response({"email_verified": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def account_summary(request):
    from datetime import date
    from catalog.i18n import translated_value_for_language
    from community.models import TitleRating, TitleReview
    from django.db.models import Avg, Count
    from library.models import EpisodeProgress, LibraryEntry, TitleCollection, TitleNote

    user = request.user
    status_counts = {
        row["status"]: row["total"]
        for row in LibraryEntry.objects.filter(user=user).values("status").annotate(total=Count("id"))
    }
    watched = EpisodeProgress.objects.filter(user=user, is_watched=True)
    watched_episodes = watched.count()
    watched_minutes = sum(value or 0 for value in watched.values_list("episode__title__duration_minutes", flat=True).iterator())
    missing_duration = watched.filter(episode__title__duration_minutes__isnull=True).count()
    watched_minutes += missing_duration * 24
    average_rating = TitleRating.objects.filter(user=user).aggregate(value=Avg("value"))["value"]

    # Favorite genres per design spec §5.3: top-5 horizontal bars derived
    # from the personal library composition.
    genre_counts: dict[object, int] = {}
    for entry in LibraryEntry.objects.filter(user=user).select_related("title").prefetch_related(
        "title__genres__translations"
    ):
        for genre in entry.title.genres.all():
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    top_genres = sorted(genre_counts.items(), key=lambda pair: (-pair[1], pair[0].slug))[:5]
    max_genre_count = top_genres[0][1] if top_genres else 0
    language = getattr(user, "preferred_language", None) or "ru"
    today = timezone.localdate()
    months = []
    year, month = today.year, today.month
    for offset in range(11, -1, -1):
        index = year * 12 + month - 1 - offset
        months.append(date(index // 12, index % 12 + 1, 1))
    activity_counts = {month: 0 for month in months}
    for watched_at in watched.exclude(watched_at=None).values_list("watched_at", flat=True):
        local = timezone.localtime(watched_at)
        key = date(local.year, local.month, 1)
        if key in activity_counts:
            activity_counts[key] += 1

    return Response({
        "library": {choice: status_counts.get(choice, 0) for choice, _ in LibraryEntry.Status.choices},
        "favorites": LibraryEntry.objects.filter(user=user, is_favorite=True).count(),
        "watched_episodes": watched_episodes,
        "watched_hours": round(watched_minutes / 60),
        "activity": [
            {"month": month.isoformat()[:7], "episodes": activity_counts[month]}
            for month in months
        ],
        "average_rating": round(average_rating, 1) if average_rating is not None else None,
        "top_genres": [
            {
                "slug": genre.slug,
                "name": translated_value_for_language(genre, "name", language),
                "count": count,
                "share": round(count * 100 / max_genre_count) if max_genre_count else 0,
            }
            for genre, count in top_genres
        ],
        "notes": TitleNote.objects.filter(user=user).count(),
        "collections": TitleCollection.objects.filter(owner=user).count(),
        "ratings": TitleRating.objects.filter(user=user).count(),
        "reviews": TitleReview.objects.filter(user=user).count(),
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def user_preferences(request):
    serializer = UserPreferencesSerializer(request.user, data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(UserSerializer(request.user).data)


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def profile_settings(request):
    if request.method == "GET":
        return Response(UserSerializer(request.user).data)
    enforce_csrf(request)
    serializer = PublicProfileUpdateSerializer(request.user, data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    if not request.user.profile_is_public:
        # Closing a profile revokes every incoming social edge immediately;
        # it cannot silently reappear in old followers' feeds if reopened.
        request.user.profile_followers.all().delete()
    return Response(UserSerializer(request.user).data)


def telegram_identity(telegram_user):
    subject = str(telegram_user["id"])
    display_name = " ".join(
        filter(None, [telegram_user.get("first_name", ""), telegram_user.get("last_name", "")])
    ).strip()
    identity = ExternalIdentity.objects.select_related("user").filter(
        provider=ExternalIdentity.Provider.TELEGRAM,
        subject=subject,
    ).first()
    if identity is None:
        user = User.objects.create_user(email=None, display_name=display_name[:80])
        identity = ExternalIdentity(user=user, provider=ExternalIdentity.Provider.TELEGRAM, subject=subject)
    else:
        user = identity.user
    identity.username = telegram_user.get("username", "")[:128]
    identity.display_name = display_name[:256]
    identity.last_authenticated_at = timezone.now()
    identity.save()
    return user


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def telegram_challenge(request):
    enforce_csrf(request)
    if request.user.is_authenticated:
        return Response({"detail": "Сначала выйдите из текущего аккаунта."}, status=409)
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_BOT_USERNAME or not settings.TELEGRAM_WEBHOOK_SECRET:
        return Response({"detail": "Вход через Telegram пока не настроен."}, status=503)
    if not request.session.session_key:
        request.session.create()
    raw_token = create_link_token()
    now = timezone.now()
    TelegramLoginChallenge.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()
    TelegramLoginChallenge.objects.filter(
        session_hash=hash_secret(request.session.session_key),
        status=TelegramLoginChallenge.Status.PENDING,
    ).update(status=TelegramLoginChallenge.Status.EXPIRED)
    TelegramLoginChallenge.objects.create(
        token_hash=hash_secret(raw_token),
        session_hash=hash_secret(request.session.session_key),
        expires_at=now + timedelta(minutes=5),
    )
    return Response({
        "token": raw_token,
        "bot_url": f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={raw_token}",
        "expires_in": 300,
    }, status=201)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def telegram_challenge_complete(request):
    enforce_csrf(request)
    raw_token = request.data.get("token")
    if not valid_link_token(raw_token) or not request.session.session_key:
        return Response({"detail": "Challenge не найден."}, status=404)
    # Cheap indexed existence check keeps junk tokens from opening the
    # row-locking transaction below.
    if not TelegramLoginChallenge.objects.filter(
        token_hash=hash_secret(raw_token),
        session_hash=hash_secret(request.session.session_key),
    ).exists():
        return Response({"detail": "Challenge не найден."}, status=404)
    with transaction.atomic():
        challenge = TelegramLoginChallenge.objects.select_for_update().filter(
            token_hash=hash_secret(raw_token),
            session_hash=hash_secret(request.session.session_key),
        ).first()
        if challenge is None:
            return Response({"detail": "Challenge не найден."}, status=404)
        if challenge.expires_at <= timezone.now() or challenge.status == TelegramLoginChallenge.Status.EXPIRED:
            challenge.status = TelegramLoginChallenge.Status.EXPIRED
            challenge.save(update_fields=["status"])
            return Response({"status": "expired"}, status=410)
        if challenge.status == TelegramLoginChallenge.Status.PENDING:
            return Response({"status": "pending"}, status=202)
        if challenge.status != TelegramLoginChallenge.Status.APPROVED or challenge.user is None:
            return Response({"status": "consumed"}, status=410)
        user = challenge.user
        if not user.is_active:
            return Response({"detail": "Аккаунт отключён."}, status=403)
        challenge.status = TelegramLoginChallenge.Status.CONSUMED
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["status", "consumed_at"])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return Response(UserSerializer(user).data)


telegram_challenge_complete.throttle_scope = "telegram_challenge"


@api_view(["POST"])
@permission_classes([AllowAny])
def telegram_webhook(request):
    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not constant_time_equals(provided_secret, settings.TELEGRAM_WEBHOOK_SECRET):
        return Response({"detail": "Forbidden"}, status=403)
    message = request.data.get("message")
    if not isinstance(message, dict):
        return Response({"ok": True})
    text = message.get("text", "")
    sender = message.get("from")
    chat = message.get("chat")
    parts = text.split(maxsplit=1) if isinstance(text, str) else []
    command = parts[0].split("@", 1)[0] if parts else ""
    if command != "/start" or len(parts) != 2 or not valid_link_token(parts[1]):
        return Response({"method": "sendMessage", "chat_id": chat.get("id") if isinstance(chat, dict) else None, "text": "Откройте вход через Telegram на сайте AniCast."})
    if not isinstance(sender, dict) or isinstance(sender.get("id"), bool) or not isinstance(sender.get("id"), int):
        return Response({"ok": True})
    with transaction.atomic():
        challenge = TelegramLoginChallenge.objects.select_for_update().filter(
            token_hash=hash_secret(parts[1]),
            status=TelegramLoginChallenge.Status.PENDING,
            expires_at__gt=timezone.now(),
        ).first()
        if challenge is None:
            reply = "Ссылка входа устарела. Создайте новую на сайте AniCast."
        else:
            try:
                with transaction.atomic():
                    user = telegram_identity(sender)
            except IntegrityError:
                identity = ExternalIdentity.objects.select_related("user").get(
                    provider=ExternalIdentity.Provider.TELEGRAM,
                    subject=str(sender["id"]),
                )
                user = identity.user
            challenge.user = user
            challenge.status = TelegramLoginChallenge.Status.APPROVED
            challenge.approved_at = timezone.now()
            challenge.save(update_fields=["user", "status", "approved_at"])
            reply = "Вход подтверждён. Вернитесь на сайт AniCast."
    return Response({"method": "sendMessage", "chat_id": chat.get("id") if isinstance(chat, dict) else sender["id"], "text": reply})
