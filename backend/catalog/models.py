from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
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
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    poster_url = models.URLField(blank=True)
    poster_origin_url = models.URLField(blank=True)
    genres = models.ManyToManyField(Genre, related_name="titles", blank=True)
    franchise = models.ForeignKey(Franchise, related_name="titles", null=True, blank=True, on_delete=models.SET_NULL)
    characters = models.ManyToManyField("Character", through="TitleCharacter", related_name="titles", blank=True)  # type: ignore[var-annotated]

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["title_type"]),
            # Every catalog page orders by (name, slug) — the model default plus
            # the unique tiebreaker. Without a matching index Postgres sorts the
            # whole table per request; measured on 60k rows, a deep page went
            # from an external merge sort (141 ms) to an index scan (23 ms), and
            # a status-filtered page from 30 ms to 11 ms.
            #
            # `ordering=recent` (year DESC NULLS LAST, name, slug) is deliberately
            # left unindexed. Matching it needs an explicit NULLS LAST index —
            # a plain DESC index does not qualify, since Postgres DESC implies
            # NULLS FIRST — and SQLite cannot create one at all, so the index
            # would exist in production but not in the test schema. At 60k rows
            # that ordering is a 25 ms top-N heapsort, and the real catalog is
            # two orders of magnitude smaller.
            models.Index(fields=["name", "slug"], name="catalog_title_name_slug_idx"),
        ]
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
    # Kodik, TVDB and TMDB all keep a work's specials in their own season zero,
    # and so does this. Without it the only home for a special is the regular
    # episode numbers, where it collides with a real episode. It is a
    # classification rather than a second key: `number` stays unique per title, so
    # watch URLs, progress and history are unaffected.
    season_number = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=240, blank=True)
    synopsis = models.TextField(blank=True)
    air_date = models.DateField(null=True, blank=True)
    # Confirmed broadcast moment. `air_date` stays the source of truth for the
    # calendar day, `air_at` is only set when the exact time is known, so the
    # schedule never invents a release time it cannot verify.
    air_at = models.DateTimeField("Точное время выхода", null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["title", "number"], name="unique_title_episode_number")]
        indexes = [
            models.Index(fields=["air_date"]),
            models.Index(fields=["air_at"]),
            models.Index(fields=["title", "season_number"]),
        ]
        verbose_name = "Эпизод"
        verbose_name_plural = "Эпизоды"

    def __str__(self) -> str:
        return f"{self.title.name} #{self.number}"

    def save(self, *args, **kwargs):
        # A confirmed exact moment always implies its calendar day, so the
        # schedule range filter and the day grouping stay consistent.
        if self.air_at is not None:
            self.air_date = timezone.localtime(self.air_at).date()
            update_fields = kwargs.get("update_fields")
            # A partial save of `air_at` alone would otherwise leave a stale
            # `air_date` in the database.
            if update_fields is not None and "air_at" in update_fields and "air_date" not in update_fields:
                kwargs["update_fields"] = [*update_fields, "air_date"]
        super().save(*args, **kwargs)


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


class Character(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    original_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    image_origin_url = models.URLField(blank=True)

    class Meta:
        ordering = ["name", "slug"]
        verbose_name = "Персонаж"
        verbose_name_plural = "Персонажи"

    def __str__(self) -> str:
        return self.name


class CharacterTranslation(models.Model):
    character = models.ForeignKey(Character, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("Язык", max_length=8, choices=LANGUAGE_CHOICES)
    name = models.CharField("Имя", max_length=200)
    description = models.TextField("Описание", blank=True)

    class Meta:
        ordering = ["language"]
        verbose_name = "Перевод персонажа"
        verbose_name_plural = "Переводы персонажа"
        constraints = [models.UniqueConstraint(fields=["character", "language"], name="unique_character_language")]


class TitleCharacter(models.Model):
    ROLE_CHOICES = [
        ("protagonist", "Главный герой"), ("supporting", "Второстепенный"),
        ("antagonist", "Антагонист"), ("cameo", "Камео"),
    ]
    title = models.ForeignKey(Title, related_name="character_links", on_delete=models.CASCADE)
    character = models.ForeignKey(Character, related_name="title_links", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="supporting")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Персонаж тайтла"
        verbose_name_plural = "Персонажи тайтла"
        constraints = [models.UniqueConstraint(fields=["title", "character"], name="unique_title_character")]


class Creator(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True)
    image_url = models.URLField(blank=True)
    image_origin_url = models.URLField(blank=True)

    class Meta:
        ordering = ["name", "id"]
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"

    def __str__(self) -> str:
        return self.name


class TitleCredit(models.Model):
    ROLE_CHOICES = [
        ("director", "Режиссёр"),
        ("producer", "Продюсер"),
        ("writer", "Сценарист"),
        ("composer", "Композитор"),
        ("designer", "Дизайнер"),
    ]
    title = models.ForeignKey(Title, related_name="credits", on_delete=models.CASCADE)
    creator = models.ForeignKey(Creator, related_name="title_credits", on_delete=models.CASCADE)
    # ``role`` is a stable source key. Exact per-work labels come from the
    # metadata source because production credits are more specific than the
    # five legacy buckets (for example episode director or series composition).
    role = models.CharField(max_length=80)
    role_ru = models.CharField(max_length=200, blank=True)
    role_en = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=32, default="manual")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Автор тайтла"
        verbose_name_plural = "Авторы тайтла"
        constraints = [models.UniqueConstraint(fields=["title", "creator", "role"], name="unique_title_creator_role")]


class MediaAsset(models.Model):
    KIND_CHOICES = [("image", "Изображение"), ("trailer", "Трейлер"), ("promo", "Промо")]
    title = models.ForeignKey(Title, related_name="media_assets", null=True, blank=True, on_delete=models.CASCADE)
    character = models.ForeignKey(Character, related_name="media_assets", null=True, blank=True, on_delete=models.CASCADE)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    url = models.URLField()
    thumbnail_url = models.URLField(blank=True)
    caption = models.CharField(max_length=240, blank=True)
    credit = models.CharField(max_length=240)
    rights_reference = models.CharField(max_length=240)
    is_published = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Медиа"
        verbose_name_plural = "Медиа"
        constraints = [
            models.CheckConstraint(
                condition=(Q(title__isnull=False, character__isnull=True) | Q(title__isnull=True, character__isnull=False)),
                name="media_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=Q(is_published=False) | ~Q(rights_reference=""),
                name="published_media_requires_rights",
            ),
        ]

    def __str__(self) -> str:
        return self.caption or f"{self.kind} #{self.pk}"


class MediaAssetTranslation(models.Model):
    asset = models.ForeignKey(MediaAsset, related_name="translations", on_delete=models.CASCADE)
    language = models.CharField("Язык", max_length=8, choices=LANGUAGE_CHOICES)
    caption = models.CharField("Подпись", max_length=240, blank=True)

    class Meta:
        ordering = ["language"]
        constraints = [models.UniqueConstraint(fields=["asset", "language"], name="unique_media_language")]


class Provider(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    website_url = models.URLField(blank=True)
    allowed_hosts = models.JSONField(default=list, blank=True)
    playback_adapter = models.CharField(max_length=64, blank=True)
    playback_config = models.JSONField(default=dict, blank=True)
    rights_reference = models.CharField(max_length=240, blank=True)
    rights_verified_at = models.DateTimeField(null=True, blank=True)
    rights_valid_until = models.DateTimeField(null=True, blank=True)
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
    external_id = models.CharField(max_length=160, blank=True)
    name = models.CharField(max_length=120)
    url = models.URLField()
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="sub")
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default="available")
    availability_reason = models.CharField(max_length=240, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    playback_count = models.PositiveBigIntegerField(default=0)

    @property
    def is_available(self) -> bool:
        return self.availability == "available"

    class Meta:
        ordering = ["name", "id"]
        indexes = [
            # The catalog "playable episodes" count filters sources by episode
            # and availability per title row; this index keeps that correlated
            # subquery on available rows instead of touching every source of a
            # long series.
            models.Index(fields=["episode", "availability"], name="src_episode_avail_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["episode", "name", "kind"],
                condition=Q(external_id=""),
                name="unique_manual_episode_source",
            ),
            models.UniqueConstraint(
                fields=["provider", "episode", "external_id"],
                condition=~Q(external_id=""),
                name="unique_provider_episode_external_source",
            ),
            models.CheckConstraint(
                condition=Q(external_id="") | Q(provider__isnull=False),
                name="external_source_requires_provider",
            ),
        ]

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
