from django.conf import settings
from django.db import models

from catalog.models import Episode, Title


class TelegramNotificationChannel(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="telegram_notification_channel", on_delete=models.CASCADE)
    telegram_user_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    def __str__(self) -> str:
        return f"{self.user} / Telegram {self.chat_id}"


class TelegramNotificationChallenge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="telegram_notification_challenges", on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at", "consumed_at"])]


class TitleNotificationSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="title_notification_subscriptions", on_delete=models.CASCADE)
    title = models.ForeignKey(Title, related_name="notification_subscriptions", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "title"], name="unique_user_title_notification")]


class NotificationDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"

    subscription = models.ForeignKey(TitleNotificationSubscription, related_name="deliveries", on_delete=models.CASCADE)
    episode = models.ForeignKey(Episode, related_name="notification_deliveries", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["subscription", "episode"], name="unique_subscription_episode_delivery")]
