from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.html import format_html
from django.utils import timezone

from push.tasks import notify_report_handled

from . import posters
from .models import (
    Character,
    CharacterTranslation,
    Creator,
    Episode,
    EpisodeTranslation,
    Franchise,
    FranchiseTranslation,
    Genre,
    GenreTranslation,
    MediaAsset,
    MediaAssetTranslation,
    Provider,
    RightsGrant,
    Source,
    SourceHealthCheck,
    SourceReport,
    Title,
    TitleCharacter,
    TitleCredit,
    TitleTranslation,
)
from .playback import source_url_allowed, validate_provider_configuration

POSTER_TIER_BADGES = {
    posters.TIER_MAXIMUM: ("m", "#1b7d54"),
    posters.TIER_LARGE: ("l", "#1d5fbf"),
    posters.TIER_KITSU: ("k", "#6b21a8"),
    posters.TIER_FALLBACK: ("s", "#b45309"),
}

SOURCE_AVAILABILITY_TONES = {
    "available": ("#e7f4ec", "#1b7d54"),
    "geo_blocked": ("#fdf3e3", "#b45309"),
    "provider_error": ("#fbe9ea", "#b3261e"),
    "unavailable": ("#efefef", "#5f5f5f"),
    "expired": ("#efefef", "#5f5f5f"),
}


def _missing_avatar_query(field: str = "image_url") -> Q:
    return Q(**{field: ""}) | Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__icontains": "missing_original"})


class AvatarStatusFilter(admin.SimpleListFilter):
    title = "аватар"
    parameter_name = "avatar"

    def lookups(self, request, model_admin):
        return (("missing", "Нет оригинального изображения"), ("present", "Есть изображение"))

    def queryset(self, request, queryset):
        missing = _missing_avatar_query()
        if self.value() == "missing":
            return queryset.filter(missing)
        if self.value() == "present":
            return queryset.exclude(missing)
        return queryset


class CharacterImportanceFilter(admin.SimpleListFilter):
    title = "значимость"
    parameter_name = "importance"

    def lookups(self, request, model_admin):
        return (("main", "Главные герои"), ("supporting", "Второстепенные"))

    def queryset(self, request, queryset):
        if self.value() == "main":
            return queryset.filter(title_links__role__in=("protagonist", "antagonist")).distinct()
        if self.value() == "supporting":
            return queryset.exclude(title_links__role__in=("protagonist", "antagonist")).distinct()
        return queryset


@admin.display(description="Аватар")
def avatar_preview(obj):
    if not obj.image_url or "missing_original" in obj.image_url:
        return format_html('<span style="color:#b45309;font-weight:600">нет</span>')
    return format_html(
        '<img src="{}" alt="" referrerpolicy="no-referrer" '
        'style="width:42px;height:42px;object-fit:cover;object-position:50% 18%;border-radius:50%" />',
        obj.image_url,
    )


class ProviderAdminForm(forms.ModelForm):
    class Meta:
        model = Provider
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        try:
            adapter, config, hosts = validate_provider_configuration(
                cleaned_data.get("playback_adapter"),
                cleaned_data.get("playback_config"),
                cleaned_data.get("allowed_hosts"),
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error
        cleaned_data["playback_adapter"] = adapter
        cleaned_data["playback_config"] = config
        cleaned_data["allowed_hosts"] = hosts
        return cleaned_data


class SourceAdminForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get("provider")
        url = cleaned_data.get("url")
        if provider is not None and url:
            candidate = Source(provider=provider, url=url)
            if not source_url_allowed(candidate):
                raise ValidationError("URL must be credential-free HTTPS on the provider allowlist.")
        return cleaned_data


class EpisodeInline(admin.TabularInline):
    model = Episode
    fields = ["number", "name", "air_date", "air_at"]
    ordering = ["number"]
    extra = 0


class GenreTranslationInline(admin.TabularInline):
    model = GenreTranslation
    extra = 1


class FranchiseTranslationInline(admin.StackedInline):
    model = FranchiseTranslation
    extra = 1


class TitleTranslationInline(admin.StackedInline):
    model = TitleTranslation
    extra = 1


class EpisodeTranslationInline(admin.StackedInline):
    model = EpisodeTranslation
    extra = 1


class CharacterTranslationInline(admin.StackedInline):
    model = CharacterTranslation
    extra = 1


class TitleCharacterInline(admin.TabularInline):
    model = TitleCharacter
    extra = 0
    autocomplete_fields = ["character"]


class TitleCreditInline(admin.TabularInline):
    model = TitleCredit
    extra = 0
    autocomplete_fields = ["creator"]


class CharacterTitleInline(admin.TabularInline):
    model = TitleCharacter
    fk_name = "character"
    extra = 0
    autocomplete_fields = ["title"]


class MediaAssetTranslationInline(admin.TabularInline):
    model = MediaAssetTranslation
    extra = 1


class TitleMediaInline(admin.TabularInline):
    model = MediaAsset
    fk_name = "title"
    fields = ["kind", "url", "thumbnail_url", "caption", "credit", "rights_reference", "is_published", "sort_order"]
    extra = 0


class CharacterMediaInline(admin.TabularInline):
    model = MediaAsset
    fk_name = "character"
    fields = ["kind", "url", "thumbnail_url", "caption", "credit", "rights_reference", "is_published", "sort_order"]
    extra = 0


class SourceInline(admin.TabularInline):
    model = Source
    form = SourceAdminForm
    fields = ["provider", "name", "kind", "url", "availability", "availability_reason", "state"]
    readonly_fields = ["state"]
    extra = 0

    @admin.display(description="Состояние")
    def state(self, obj: Source | None):
        if obj is None or obj.pk is None:
            return "—"
        return availability_pill(obj)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [GenreTranslationInline]


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order"]
    search_fields = ["name", "slug"]
    ordering = ["sort_order", "name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [FranchiseTranslationInline]


@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ["poster_thumb", "name", "poster_tier", "title_type", "status", "year", "franchise"]
    list_display_links = ["name"]
    list_filter = ["title_type", "status", "genres"]
    search_fields = ["name", "original_name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["genres"]
    list_select_related = ["franchise"]
    readonly_fields = ["poster_preview"]
    fieldsets = [
        (None, {"fields": ["name", "original_name", "slug", "synopsis"]}),
        ("Классификация", {"fields": ["title_type", "status", "year", "genres", "franchise"]}),
        ("Постер", {"fields": ["poster_preview", "poster_url"], "description": "Локальное зеркало пополняется автоматически; ручная правка URL — только для восстановления источников."}),
    ]
    inlines = [TitleTranslationInline, EpisodeInline, TitleCharacterInline, TitleCreditInline, TitleMediaInline]

    @admin.display(description="Постер")
    def poster_thumb(self, obj: Title):
        if not obj.poster_url:
            return "—"
        return format_html(
            '<img src="{}" alt="" referrerpolicy="no-referrer" loading="lazy" '
            'style="width:42px;height:auto;border-radius:4px;border:1px solid #ccc;display:block" />',
            obj.poster_url,
        )

    @admin.display(description="Тир")
    def poster_tier(self, obj: Title):
        tier = posters.current_tier(obj.poster_url or "")
        if tier is None:
            return format_html('<span style="color:#8a8a8a">нет</span>')
        label, color = POSTER_TIER_BADGES.get(tier, (tier, "#5f5f5f"))
        return format_html(
            '<span title="{}" style="padding:2px 9px;border-radius:10px;background:{};color:#fff;font-size:11px;font-weight:600">{}</span>',
            f"качество постера: {label}",
            color,
            label,
        )

    @admin.display(description="Текущий постер")
    def poster_preview(self, obj: Title):
        if not obj.poster_url:
            return "Постера нет — очередь автоапгрейда подберёт арт сама."
        tier = posters.current_tier(obj.poster_url) or ""
        return format_html(
            '<img src="{}" alt="" referrerpolicy="no-referrer" '
            'style="max-width:180px;border-radius:6px;border:1px solid #ccc;display:block;margin-bottom:4px" />'
            '<div style="font-size:11px;color:#666">тир: {}</div>',
            obj.poster_url,
            tier or "внешний источник",
        )


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ["title", "number", "name", "air_date", "air_at"]
    list_filter = ["air_date"]
    search_fields = ["title__name", "name"]
    autocomplete_fields = ["title"]
    date_hierarchy = "air_date"
    inlines = [EpisodeTranslationInline, SourceInline]


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = [avatar_preview, "name", "original_name", "slug"]
    list_filter = [AvatarStatusFilter, CharacterImportanceFilter]
    search_fields = ["name", "original_name", "slug", "translations__name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CharacterTranslationInline, CharacterTitleInline, CharacterMediaInline]


@admin.register(Creator)
class CreatorAdmin(admin.ModelAdmin):
    list_display = [avatar_preview, "name", "slug", "image_url"]
    list_filter = [AvatarStatusFilter]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["caption", "kind", "title", "character", "credit", "is_published", "sort_order"]
    list_filter = ["kind", "is_published"]
    search_fields = ["caption", "credit", "rights_reference", "title__name", "character__name"]
    autocomplete_fields = ["title", "character"]
    inlines = [MediaAssetTranslationInline]


def availability_pill(source: Source):
    """Colour-coded availability state; statuses never rely on colour alone."""
    text = source.get_availability_display()
    background, color = SOURCE_AVAILABILITY_TONES.get(source.availability, ("#efefef", "#5f5f5f"))
    return format_html(
        '<span style="padding:2px 9px;border-radius:10px;background:{};color:{};font-size:11px;font-weight:600">{}</span>',
        background,
        color,
        text,
    )


class SourceHealthCheckInline(admin.TabularInline):
    model = SourceHealthCheck
    fk_name = "source"
    extra = 0
    can_delete = False
    fields = ["checked_at", "is_healthy", "http_status", "latency_ms", "error"]
    readonly_fields = ["checked_at", "is_healthy", "http_status", "latency_ms", "error"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    form = SourceAdminForm
    list_display = ["episode", "provider", "name", "kind", "availability_badge", "last_http_status", "consecutive_failures", "last_checked_at"]
    list_filter = ["kind", "availability"]
    search_fields = ["name", "episode__title__name"]
    autocomplete_fields = ["episode", "provider"]
    readonly_fields = ["last_checked_at", "last_http_status", "consecutive_failures"]
    inlines = [SourceHealthCheckInline]

    @admin.display(description="Доступность", ordering="availability")
    def availability_badge(self, obj: Source):
        return availability_pill(obj)


@admin.register(SourceHealthCheck)
class SourceHealthCheckAdmin(admin.ModelAdmin):
    list_display = ["source", "is_healthy", "http_status", "latency_ms", "checked_at"]
    list_filter = ["is_healthy", "checked_at"]
    search_fields = ["source__name", "source__episode__title__name", "error"]
    readonly_fields = ["source", "checked_at", "is_healthy", "http_status", "latency_ms", "error"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    form = ProviderAdminForm
    list_display = ["name", "slug", "is_enabled", "updated_at"]
    list_filter = ["is_enabled"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    fields = ["name", "slug", "website_url", "allowed_hosts", "playback_adapter", "playback_config", "is_enabled"]


@admin.register(RightsGrant)
class RightsGrantAdmin(admin.ModelAdmin):
    list_display = ["source", "status", "valid_from", "valid_until", "approved_by", "approved_at"]
    list_filter = ["status", "valid_from", "valid_until"]
    search_fields = ["source__episode__title__name", "source__name", "contract_reference"]
    autocomplete_fields = ["source"]
    readonly_fields = ["status", "approved_by", "approved_at", "revoked_at", "created_at", "updated_at"]
    actions = ["activate_grants", "revoke_grants"]

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Активировать права")
    def activate_grants(self, request, queryset):
        for grant in queryset.select_related("source__provider"):
            if grant.status != RightsGrant.Status.DRAFT or not grant.source.provider or not grant.source.provider.is_enabled:
                continue
            if not source_url_allowed(grant.source):
                continue
            grant.status = RightsGrant.Status.ACTIVE
            grant.approved_by = request.user
            grant.approved_at = timezone.now()
            grant.revoked_at = None
            grant.save(update_fields=["status", "approved_by", "approved_at", "revoked_at", "updated_at"])
            self.log_change(request, grant, "Права активированы.")

    @admin.action(description="Отозвать права")
    def revoke_grants(self, request, queryset):
        for grant in queryset.filter(status=RightsGrant.Status.ACTIVE):
            grant.status = RightsGrant.Status.REVOKED
            grant.revoked_at = timezone.now()
            grant.save(update_fields=["status", "revoked_at", "updated_at"])
            self.log_change(request, grant, "Права отозваны.")


@admin.register(SourceReport)
class SourceReportAdmin(admin.ModelAdmin):
    list_display = ["source", "reason", "status", "reporter", "created_at", "handled_by"]
    list_filter = ["status", "reason", "created_at"]
    search_fields = ["source__name", "source__episode__title__name", "reporter__email", "reporter__display_name", "message"]
    readonly_fields = ["source", "reporter", "reason", "message", "created_at", "updated_at", "handled_by", "handled_at"]
    actions = ["mark_reviewing", "mark_resolved", "mark_rejected"]
    list_select_related = ["source", "source__episode", "source__episode__title", "reporter", "handled_by"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if obj.status != SourceReport.Status.NEW:
            obj.handled_by = request.user
            obj.handled_at = timezone.now()
        super().save_model(request, obj, form, change)

    def set_status(self, request, queryset, report_status):
        now = timezone.now()
        for report in queryset:
            previous = report.status
            report.status = report_status
            report.handled_by = request.user
            report.handled_at = now
            report.save(update_fields=["status", "handled_by", "handled_at", "updated_at"])
            self.log_change(request, report, f"Статус изменён на «{report.get_status_display()}».")
            # Only a final verdict reaches the reporter; "reviewing" is an
            # internal stage and re-applying the same status is silent.
            if previous != report_status and report_status in {SourceReport.Status.RESOLVED, SourceReport.Status.REJECTED}:
                if report.reporter != request.user:
                    notify_report_handled(report)

    @admin.action(description="Взять на проверку")
    def mark_reviewing(self, request, queryset):
        self.set_status(request, queryset, SourceReport.Status.REVIEWING)

    @admin.action(description="Отметить решёнными")
    def mark_resolved(self, request, queryset):
        self.set_status(request, queryset, SourceReport.Status.RESOLVED)

    @admin.action(description="Отклонить")
    def mark_rejected(self, request, queryset):
        self.set_status(request, queryset, SourceReport.Status.REJECTED)
