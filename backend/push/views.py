import hmac
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.telegram_bot import create_challenge_token, hash_secret, valid_challenge_token
from catalog.models import Title
from library.views import LibraryPagination

from .models import TelegramNotificationChallenge, TelegramNotificationChannel, TitleNotificationSubscription
from .serializers import ChannelSerializer, SubscriptionSerializer


class NotificationChallengeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not settings.TELEGRAM_NOTIFY_BOT_TOKEN or not settings.TELEGRAM_NOTIFY_BOT_USERNAME or not settings.TELEGRAM_NOTIFY_WEBHOOK_SECRET:
            return Response({"detail": "Бот уведомлений пока не настроен."}, status=503)
        now = timezone.now()
        TelegramNotificationChallenge.objects.filter(user=request.user, consumed_at__isnull=True).delete()
        TelegramNotificationChallenge.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()
        token = create_challenge_token()
        TelegramNotificationChallenge.objects.create(
            user=request.user,
            token_hash=hash_secret(token),
            expires_at=now + timedelta(minutes=10),
        )
        return Response({
            "bot_url": f"https://t.me/{settings.TELEGRAM_NOTIFY_BOT_USERNAME}?start={token}",
            "expires_in": 600,
        }, status=201)


class NotificationChannelView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        channel = TelegramNotificationChannel.objects.filter(user=request.user).first()
        return Response({"connected": bool(channel and channel.is_active), "channel": ChannelSerializer(channel).data if channel else None})

    def delete(self, request):
        channel = get_object_or_404(TelegramNotificationChannel, user=request.user)
        channel.is_active = False
        channel.disabled_at = timezone.now()
        channel.save(update_fields=["is_active", "disabled_at", "updated_at"])
        return Response(status=204)


class SubscriptionListView(ListAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LibraryPagination

    def get_queryset(self):
        return TitleNotificationSubscription.objects.filter(user=self.request.user).select_related("title")


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        subscription = get_object_or_404(TitleNotificationSubscription.objects.select_related("title"), user=request.user, title__slug=slug)
        return Response(SubscriptionSerializer(subscription).data)

    def put(self, request, slug):
        title = get_object_or_404(Title, slug=slug)
        subscription, created = TitleNotificationSubscription.objects.update_or_create(
            user=request.user, title=title, defaults={"is_active": True}
        )
        return Response(SubscriptionSerializer(subscription).data, status=201 if created else 200)

    def delete(self, request, slug):
        subscription = get_object_or_404(TitleNotificationSubscription, user=request.user, title__slug=slug)
        subscription.delete()
        return Response(status=204)


@api_view(["POST"])
@permission_classes([AllowAny])
def notification_webhook(request):
    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.TELEGRAM_NOTIFY_WEBHOOK_SECRET or not hmac.compare_digest(provided, settings.TELEGRAM_NOTIFY_WEBHOOK_SECRET):
        return Response({"detail": "Forbidden"}, status=403)
    message = request.data.get("message")
    if not isinstance(message, dict):
        return Response({"ok": True})
    sender, chat, text = message.get("from"), message.get("chat"), message.get("text", "")
    if not isinstance(sender, dict) or not isinstance(chat, dict) or chat.get("type") != "private":
        return Response({"ok": True})
    chat_id, telegram_user_id = chat.get("id"), sender.get("id")
    if not isinstance(chat_id, int) or not isinstance(telegram_user_id, int):
        return Response({"ok": True})
    parts = text.split(maxsplit=1) if isinstance(text, str) else []
    command = parts[0].split("@", 1)[0] if parts else ""
    if command == "/stop":
        TelegramNotificationChannel.objects.filter(chat_id=chat_id).update(
            is_active=False, disabled_at=timezone.now(), updated_at=timezone.now()
        )
        return Response({"method": "sendMessage", "chat_id": chat_id, "text": "Уведомления AniCast отключены."})
    if command != "/start" or len(parts) != 2 or not valid_challenge_token(parts[1]):
        return Response({"method": "sendMessage", "chat_id": chat_id, "text": "Подключите уведомления в настройках аккаунта AniCast."})
    with transaction.atomic():
        challenge = TelegramNotificationChallenge.objects.select_for_update().filter(
            token_hash=hash_secret(parts[1]), consumed_at__isnull=True, expires_at__gt=timezone.now()
        ).select_related("user").first()
        if challenge is None:
            text_response = "Ссылка устарела. Создайте новую в аккаунте AniCast."
        elif TelegramNotificationChannel.objects.exclude(user=challenge.user).filter(chat_id=chat_id).exists():
            text_response = "Этот Telegram уже связан с другим аккаунтом AniCast."
        else:
            try:
                TelegramNotificationChannel.objects.update_or_create(
                    user=challenge.user,
                    defaults={
                        "telegram_user_id": telegram_user_id,
                        "chat_id": chat_id,
                        "username": str(sender.get("username", ""))[:128],
                        "is_active": True,
                        "disabled_at": None,
                        "last_error": "",
                    },
                )
            except IntegrityError:
                text_response = "Не удалось связать Telegram с аккаунтом."
            else:
                challenge.consumed_at = timezone.now()
                challenge.save(update_fields=["consumed_at"])
                text_response = "Уведомления AniCast подключены."
    return Response({"method": "sendMessage", "chat_id": chat_id, "text": text_response})
