from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils.text import slugify

LANGUAGE_CHOICES = [
    ("ru", "Русский"), ("en", "English"), ("uk", "Українська"), ("be", "Беларуская"),
    ("kk", "Қазақша"), ("de", "Deutsch"), ("fr", "Français"), ("es", "Español"),
    ("it", "Italiano"), ("ja", "日本語"), ("ko", "한국어"), ("zh", "中文"),
]


class Genre(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"

    def __str__(self) -> str:
        return self.name


class GenreTranslation(models.Model):
    genre = models.ForeignKey(Genre, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("Язык", max_length=8, choices=LANGUAGE_CHOICES)
    name = models.CharField("Название", max_length=80)

    class Meta:
        ordering = ["language"]
        verbose_name = "Перевод жанра"
        verbose_name_plural = "Переводы жанра"
        constraints = [models.UniqueConstraint(fields=["genre", "language"], name="unique_genre_language")]

    def __str__(self) -> str:
        return f"{self.genre.slug} / {self.language}"


class Franchise(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Франшиза"
        verbose_name_plural = "Франшизы"

    def __str__(self) -> str:
        return self.name


class FranchiseTranslation(models.Model):
    franchise = models.ForeignKey(Franchise, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("Язык", max_length=8, choices=LANGUAGE_CHOICES)
    name = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)

    class Meta:
        ordering = ["language"]
        verbose_name = "Перевод франшизы"
        verbose_name_plural = "Переводы франшизы"
        constraints = [models.UniqueConstraint(fields=["franchise", "language"], name="unique_franchise_language")]

    def __str__(self) -> str:
        return f"{self.franchise.slug} / {self.language}"


class Title(models.Model):
    TYPE_CHOICES = [("anime", "Anime"), ("movie", "Movie"), ("ova", "OVA"), ("special", "Special")]
    STATUS_CHOICES = [("ongoing", "Ongoing"), ("finished", "Finished"), ("planned", "Planned")]

    name = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260, unique=True)
    original_name = models.CharField(max_length=240, blank=True)
    synopsis = models.TextField(blank=True)
    title_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="anime")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    poster_url = models.URLField(blank=True)
    genres = models.ManyToManyField(Genre, related_name="titles", blank=True)
    franchise = models.ForeignKey(Franchise, related_name="titles", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["title_type"])]
        verbose_name = "Тайтл"
        verbose_name_plural = "Тайтлы"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class TitleTranslation(models.Model):
    title = models.ForeignKey(Title, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("Язык", max_length=8, choices=LANGUAGE_CHOICES)
    name = models.CharField("Название", max_length=240)
    synopsis = models.TextField("Описание", blank=True)

    class Meta:
        ordering = ["language"]
        verbose_name = "Перевод тайтла"
        verbose_name_plural = "Переводы тайтла"
        constraints = [models.UniqueConstraint(fields=["title", "language"], name="unique_title_language")]

    def __str__(self) -> str:
        return f"{self.title.slug} / {self.language}"


class Episode(models.Model):
    title = models.ForeignKey(Title, related_name="episodes", on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=240, blank=True)
    synopsis = models.TextField(blank=True)
    air_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["title", "number"], name="unique_title_episode_number")]
        verbose_name = "Эпизод"
        verbose_name_plural = "Эпизоды"

    def __str__(self) -> str:
        return f"{self.title.name} #{self.number}"


class EpisodeTranslation(models.Model):
    episode = models.ForeignKey(Episode, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("Язык", max_length=8, choices=LANGUAGE_CHOICES)
    name = models.CharField("Название", max_length=240, blank=True)
    synopsis = models.TextField("Описание", blank=True)

    class Meta:
        ordering = ["language"]
        verbose_name = "Перевод эпизода"
        verbose_name_plural = "Переводы эпизода"
        constraints = [models.UniqueConstraint(fields=["episode", "language"], name="unique_episode_language")]

    def __str__(self) -> str:
        return f"{self.episode} / {self.language}"


class Provider(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    website_url = models.URLField(blank=True)
    allowed_hosts = models.JSONField(default=list, blank=True)
    is_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Source(models.Model):
    KIND_CHOICES = [("sub", "Sub"), ("dub", "Dub"), ("raw", "Raw")]
    AVAILABILITY_CHOICES = [
        ("available", "Available"),
        ("unavailable", "Unavailable"),
        ("geo_blocked", "Geo blocked"),
        ("expired", "Expired"),
        ("provider_error", "Provider error"),
    ]
    episode = models.ForeignKey(Episode, related_name="sources", on_delete=models.CASCADE)
    provider = models.ForeignKey(Provider, related_name="sources", null=True, blank=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    url = models.URLField()
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="sub")
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default="available")
    availability_reason = models.CharField(max_length=240, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    consecutive_failures = models.PositiveSmallIntegerField(default=0)

    @property
    def is_available(self) -> bool:
        return self.availability == "available"

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["episode", "name", "kind"], name="unique_episode_source")]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"


class SourceHealthCheck(models.Model):
    source = models.ForeignKey(Source, related_name="health_checks", on_delete=models.CASCADE)
    checked_at = models.DateTimeField(auto_now_add=True)
    is_healthy = models.BooleanField()
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-checked_at", "-id"]
        indexes = [models.Index(fields=["source", "checked_at"])]

    def __str__(self) -> str:
        return f"{self.source} / {self.checked_at}"


class RightsGrant(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        ACTIVE = "active", "Активно"
        REVOKED = "revoked", "Отозвано"

    source = models.ForeignKey(Source, related_name="rights_grants", on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    contract_reference = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="approved_rights_grants",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(valid_until__gt=F("valid_from")), name="rights_grant_valid_interval"),
            models.UniqueConstraint(fields=["source"], condition=Q(status="active"), name="one_active_grant_per_source"),
        ]

    def __str__(self) -> str:
        return f"{self.source} — {self.get_status_display()}"


class SourceReport(models.Model):
    class Reason(models.TextChoices):
        UNAVAILABLE = "unavailable", "Источник не открывается"
        WRONG_CONTENT = "wrong_content", "Неверный эпизод или контент"
        GEO_BLOCKED = "geo_blocked", "Недоступно в регионе"
        QUALITY = "quality", "Проблема качества"
        OTHER = "other", "Другое"

    class Status(models.TextChoices):
        NEW = "new", "Новая"
        REVIEWING = "reviewing", "На проверке"
        RESOLVED = "resolved", "Решена"
        REJECTED = "rejected", "Отклонена"

    source = models.ForeignKey(Source, related_name="reports", on_delete=models.CASCADE)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="source_reports", on_delete=models.CASCADE)
    reason = models.CharField(max_length=32, choices=Reason.choices)
    message = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    resolution_note = models.CharField(max_length=500, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="handled_source_reports",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "reporter", "reason"],
                condition=Q(status__in=["new", "reviewing"]),
                name="unique_open_source_report",
            )
        ]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.source} — {self.get_reason_display()}"
