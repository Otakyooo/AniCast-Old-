from django.conf import settings
from django.contrib.auth import login, logout
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .models import ExternalIdentity, User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .telegram import TelegramAuthError, verify_telegram_payload


class AuthRateThrottle(AnonRateThrottle):
    rate = "10/min"


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


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def telegram_login(request):
    enforce_csrf(request)
    if request.user.is_authenticated:
        return Response({"detail": "Сначала выйдите из текущего аккаунта."}, status=409)
    if not settings.TELEGRAM_BOT_TOKEN:
        return Response({"detail": "Вход через Telegram пока не настроен."}, status=503)

    try:
        payload = verify_telegram_payload(request.data, settings.TELEGRAM_BOT_TOKEN)
    except TelegramAuthError as error:
        return Response({"detail": str(error), "code": error.code}, status=400)
    payload_hash = request.data["hash"]
    if not cache.add(f"telegram-login-used:{payload_hash}", True, timeout=330):
        return Response({"detail": "Эти данные Telegram уже использованы.", "code": "telegram_auth_replayed"}, status=400)

    subject = str(payload["id"])
    display_name = " ".join(filter(None, [payload.get("first_name", ""), payload.get("last_name", "")])).strip()
    try:
        with transaction.atomic():
            identity = ExternalIdentity.objects.select_related("user").filter(
                provider=ExternalIdentity.Provider.TELEGRAM,
                subject=subject,
            ).first()
            created = identity is None
            if identity is None:
                user = User.objects.create_user(email=None, display_name=display_name[:80])
                identity = ExternalIdentity(user=user, provider=ExternalIdentity.Provider.TELEGRAM, subject=subject)
            else:
                user = identity.user
            identity.username = payload.get("username", "")
            identity.display_name = display_name
            identity.avatar_url = payload.get("photo_url", "")
            identity.last_authenticated_at = timezone.now()
            identity.save()
    except IntegrityError:
        identity = ExternalIdentity.objects.select_related("user").get(
            provider=ExternalIdentity.Provider.TELEGRAM,
            subject=subject,
        )
        user = identity.user
        created = False
    if not user.is_active:
        return Response({"detail": "Аккаунт отключён."}, status=403)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return Response(UserSerializer(user).data, status=201 if created else 200)
