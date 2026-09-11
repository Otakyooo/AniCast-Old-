import uuid
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager


class User(AbstractUser):
    LANGUAGE_CHOICES = [("ru", "Русский"), ("en", "English")]
    username = None  # type: ignore[assignment]
    email = models.EmailField(unique=True, null=True, blank=True)  # type: ignore[assignment]
    display_name = models.CharField(max_length=80, blank=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    bio = models.CharField("О себе", max_length=280, blank=True)
    profile_is_public = models.BooleanField("Публичный профиль", default=False)
    preferred_language = models.CharField("Язык интерфейса", max_length=8, choices=LANGUAGE_CHOICES, default="ru")
    # When enabled, the first playback of a title adds it to the library as
    # "watching" so the shelf counters and the resume shelf stop disagreeing.
    auto_add_to_watching = models.BooleanField("Автоматически добавлять в «Смотрю»", default=False)
    # Null until the address is proven. Registration accepted any address, so a
    # typo silently produced an account whose password could never be recovered
    # and whose mail went to a stranger. Confirmation is not required to use the
    # site — locking existing accounts out would be worse than the problem — but
    # it is required before anything is sent to that address on someone's behalf.
    email_verified_at = models.DateTimeField("Адрес подтверждён", null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [models.UniqueConstraint(Lower("email"), name="unique_user_email_ci")]

    def __str__(self) -> str:
        return self.email or self.display_name or f"User {self.pk}"

    @property
    def email_is_verified(self) -> bool:
        return self.email_verified_at is not None


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


class AccountToken(models.Model):
    """Single-use link secret for password reset and address confirmation.

    Only the SHA-256 of the token is stored, like ``TelegramLoginChallenge``: a
    database read must not yield a working link. A row rather than a signed
    payload (``django.core.signing``) because these links need properties a
    signature cannot give — single use, explicit revocation when a password
    changes, and a visible audit trail of what was issued and consumed.

    ``email`` records the address the link was sent to. Confirmation must prove
    that address, not whatever the account holds when the link is opened, or
    changing the address after requesting a link would confirm the new one.
    """

    class Purpose(models.TextChoices):
        PASSWORD_RESET = "password_reset", "Сброс пароля"
        EMAIL_VERIFICATION = "email_verification", "Подтверждение адреса"

    user = models.ForeignKey(User, related_name="account_tokens", on_delete=models.CASCADE)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    email = models.EmailField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["purpose", "expires_at"]),
            models.Index(fields=["user", "purpose", "consumed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.purpose} for user {self.user_id}"


class AccountEmail(models.Model):
    """Delivery ledger for account mail; the row is what guarantees delivery.

    Same shape as ``push.EventNotification``: the request writes a PENDING row
    and only then enqueues, so an unavailable broker delays a reset link instead
    of losing it, and every outcome is visible in /staff/.

    The link secret is deliberately absent from this table. The token is minted
    inside the delivery attempt (:func:`accounts.tasks.dispatch_account_emails`),
    so a working link never exists at rest — only its hash in
    :class:`AccountToken`. That also means the link's lifetime starts when the
    mail actually goes out, not when it was queued.
    """

    class Kind(models.TextChoices):
        PASSWORD_RESET = "password_reset", "Сброс пароля"
        EMAIL_VERIFICATION = "email_verification", "Подтверждение адреса"
        PASSWORD_CHANGED = "password_changed", "Пароль изменён"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"
        EXPIRED = "expired", "Устарело"

    user = models.ForeignKey(User, related_name="account_emails", on_delete=models.CASCADE)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    to_address = models.EmailField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    token = models.OneToOneField(
        AccountToken, related_name="delivery", null=True, blank=True, on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.kind} → {self.to_address} ({self.status})"
