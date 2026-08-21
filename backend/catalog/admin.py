from django.contrib import admin
from django.utils import timezone

from .models import (
    Episode,
    EpisodeTranslation,
    Franchise,
    FranchiseTranslation,
    Genre,
    GenreTranslation,
    Provider,
    RightsGrant,
    Source,
    SourceHealthCheck,
    SourceReport,
    Title,
    TitleTranslation,
)
from .playback import source_url_allowed


class EpisodeInline(admin.TabularInline):
    model = Episode
    fields = ["number", "name", "air_date"]
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


class SourceInline(admin.TabularInline):
    model = Source
    fields = ["provider", "name", "kind", "url", "availability", "availability_reason"]
    extra = 0


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
    list_display = ["name", "title_type", "status", "year", "franchise"]
    list_filter = ["title_type", "status", "genres"]
    search_fields = ["name", "original_name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["genres"]
    list_select_related = ["franchise"]
    inlines = [TitleTranslationInline, EpisodeInline]


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ["title", "number", "name", "air_date"]
    list_filter = ["air_date"]
    search_fields = ["title__name", "name"]
    autocomplete_fields = ["title"]
    date_hierarchy = "air_date"
    inlines = [EpisodeTranslationInline, SourceInline]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["episode", "provider", "name", "kind", "availability", "last_http_status", "consecutive_failures", "last_checked_at"]
    list_filter = ["kind", "availability"]
    search_fields = ["name", "episode__title__name"]
    autocomplete_fields = ["episode", "provider"]
    readonly_fields = ["last_checked_at", "last_http_status", "consecutive_failures"]


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
    list_display = ["name", "slug", "is_enabled", "updated_at"]
    list_filter = ["is_enabled"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


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
            report.status = report_status
            report.handled_by = request.user
            report.handled_at = now
            report.save(update_fields=["status", "handled_by", "handled_at", "updated_at"])
            self.log_change(request, report, f"Статус изменён на «{report.get_status_display()}».")

    @admin.action(description="Взять на проверку")
    def mark_reviewing(self, request, queryset):
        self.set_status(request, queryset, SourceReport.Status.REVIEWING)

    @admin.action(description="Отметить решёнными")
    def mark_resolved(self, request, queryset):
        self.set_status(request, queryset, SourceReport.Status.RESOLVED)

    @admin.action(description="Отклонить")
    def mark_rejected(self, request, queryset):
        self.set_status(request, queryset, SourceReport.Status.REJECTED)
