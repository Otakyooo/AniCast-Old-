from django.conf import settings
from django.db import models

from catalog.models import Episode, Title


class TelegramNotificationChannel(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="telegram_notification_channel", on_delete=models.CASCADE)
    telegram_user_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    schedule_digest_enabled = models.BooleanField(default=False)
    last_digest_date = models.DateField(null=True, blank=True)
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


class EventNotification(models.Model):
    """One-shot push outside the episode pipeline: moderation outcomes.

    The row is the delivery ledger itself — a beat task retries PENDING rows
    (attempts < 3) exactly like episode deliveries, so an absent broker never
    loses a notification and staff can diagnose every outcome in /staff/.
    """

    class Kind(models.TextChoices):
        REVIEW_APPROVED = "review_approved", "Рецензия одобрена"
        REVIEW_REJECTED = "review_rejected", "Рецензия отклонена"
        REPORT_RESOLVED = "report_resolved", "Жалоба решена"
        REPORT_REJECTED = "report_rejected", "Жалоба отклонена"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SKIPPED = "skipped", "Канал не подключён"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="event_notifications", on_delete=models.CASCADE)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    context = models.CharField(max_length=200, blank=True)
    url_path = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "created_at"])]
