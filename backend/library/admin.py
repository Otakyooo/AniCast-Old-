from django.contrib import admin

from .models import EpisodeProgress, LibraryEntry, TitleNote


class ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LibraryEntry)
class LibraryEntryAdmin(ReadOnlyAdmin):
    list_display = ["user", "title", "status", "is_favorite", "updated_at"]
    list_filter = ["status", "is_favorite", "updated_at"]
    search_fields = ["user__email", "user__display_name", "title__name"]
    list_select_related = ["user", "title"]


@admin.register(EpisodeProgress)
class EpisodeProgressAdmin(ReadOnlyAdmin):
    list_display = ["user", "episode", "is_watched", "last_opened_at", "watched_at"]
    list_filter = ["is_watched", "last_opened_at"]
    search_fields = ["user__email", "user__display_name", "episode__title__name"]
    list_select_related = ["user", "episode", "episode__title"]


@admin.register(TitleNote)
class TitleNoteAdmin(ReadOnlyAdmin):
    list_display = ["user", "title", "updated_at"]
    search_fields = ["user__email", "user__display_name", "title__name"]
    list_select_related = ["user", "title"]
