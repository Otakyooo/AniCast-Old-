from django.contrib import admin
from django.utils import timezone

from .models import Episode, Franchise, Genre, Source, SourceReport, Title


class EpisodeInline(admin.TabularInline):
    model = Episode
    fields = ["number", "name", "air_date"]
    ordering = ["number"]
    extra = 0


class SourceInline(admin.TabularInline):
    model = Source
    fields = ["name", "kind", "url", "availability", "availability_reason"]
    extra = 0


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order"]
    search_fields = ["name", "slug"]
    ordering = ["sort_order", "name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ["name", "title_type", "status", "year", "franchise"]
    list_filter = ["title_type", "status", "genres"]
    search_fields = ["name", "original_name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["genres"]
    list_select_related = ["franchise"]
    inlines = [EpisodeInline]


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ["title", "number", "name", "air_date"]
    list_filter = ["air_date"]
    search_fields = ["title__name", "name"]
    autocomplete_fields = ["title"]
    date_hierarchy = "air_date"
    inlines = [SourceInline]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["episode", "name", "kind", "availability"]
    list_filter = ["kind", "availability"]
    search_fields = ["name", "episode__title__name"]
    autocomplete_fields = ["episode"]


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
