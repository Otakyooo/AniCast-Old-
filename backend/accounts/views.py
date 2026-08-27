import hmac
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login, logout
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

from .models import ExternalIdentity, TelegramLoginChallenge, User
from .serializers import (
    LoginSerializer,
    PublicProfileUpdateSerializer,
    RegisterSerializer,
    UserPreferencesSerializer,
    UserSerializer,
)
from .telegram_bot import create_challenge_token, hash_secret, valid_challenge_token


class AuthRateThrottle(SimpleRateThrottle):
    """IP-scoped auth throttle that also applies to authenticated callers.

    DRF's AnonRateThrottle skips logged-in requests entirely, which let a
    single throwaway session brute-force login at unlimited rate.
    """

    scope = "auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def enforce_csrf(request):
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def register(request):
    enforce_csrf(request)
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        user = serializer.save()
    except IntegrityError:
        return Response({"email": ["Аккаунт с таким email уже существует."]}, status=400)
    login(request, user)
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
    raw_token = create_challenge_token()
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
    if not valid_challenge_token(raw_token) or not request.session.session_key:
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
    if not settings.TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(provided_secret, settings.TELEGRAM_WEBHOOK_SECRET):
        return Response({"detail": "Forbidden"}, status=403)
    message = request.data.get("message")
    if not isinstance(message, dict):
        return Response({"ok": True})
    text = message.get("text", "")
    sender = message.get("from")
    chat = message.get("chat")
    parts = text.split(maxsplit=1) if isinstance(text, str) else []
    command = parts[0].split("@", 1)[0] if parts else ""
    if command != "/start" or len(parts) != 2 or not valid_challenge_token(parts[1]):
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
