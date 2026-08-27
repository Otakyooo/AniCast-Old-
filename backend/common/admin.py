from django.contrib import admin

from common.models import AvailabilitySample, DailyVisitStat


@admin.register(AvailabilitySample)
class AvailabilitySampleAdmin(admin.ModelAdmin):
    """Read-only probe log: uptime state is derived, never hand-edited."""

    list_display = ("target", "checked_at", "ok", "latency_ms", "status_code", "detail")
    list_filter = ("target", "ok")
    date_hierarchy = "checked_at"
    search_fields = ("detail",)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(DailyVisitStat)
class DailyVisitStatAdmin(admin.ModelAdmin):
    list_display = ("day", "visits", "updated_at")
    date_hierarchy = "day"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
