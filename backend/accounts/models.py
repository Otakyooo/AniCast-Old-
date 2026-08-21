from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager


class User(AbstractUser):
    username = None  # type: ignore[assignment]
    email = models.EmailField(unique=True, null=True, blank=True)  # type: ignore[assignment]
    display_name = models.CharField(max_length=80, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [models.UniqueConstraint(Lower("email"), name="unique_user_email_ci")]

    def __str__(self) -> str:
        return self.email or self.display_name or f"User {self.pk}"


class ExternalIdentity(models.Model):
    class Provider(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"

    user = models.ForeignKey(User, related_name="external_identities", on_delete=models.CASCADE)
    provider = models.CharField(max_length=32, choices=Provider.choices)
    subject = models.CharField(max_length=128)
    username = models.CharField(max_length=128, blank=True)
    display_name = models.CharField(max_length=256, blank=True)
    avatar_url = models.URLField(max_length=2048, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_authenticated_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "subject"], name="unique_external_identity")]

    def __str__(self) -> str:
        return f"{self.provider}:{self.subject}"


class TelegramLoginChallenge(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        CONSUMED = "consumed", "Consumed"
        EXPIRED = "expired", "Expired"

    token_hash = models.CharField(max_length=64, unique=True)
    session_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    user = models.ForeignKey(User, related_name="telegram_login_challenges", null=True, blank=True, on_delete=models.SET_NULL)
    expires_at = models.DateTimeField()
    approved_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "expires_at"])]

    def __str__(self) -> str:
        return f"Telegram challenge {self.pk} ({self.status})"
