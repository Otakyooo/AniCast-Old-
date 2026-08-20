from django.contrib import admin

from .models import Episode, Franchise, Genre, Source, Title


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order"]
    search_fields = ["name", "slug"]
    ordering = ["sort_order", "name"]


@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ["name", "title_type", "status", "year", "franchise"]
    list_filter = ["title_type", "status", "genres"]
    search_fields = ["name", "original_name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["genres"]


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ["title", "number", "name", "air_date"]
    list_filter = ["air_date"]
    search_fields = ["title__name", "name"]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["episode", "name", "kind", "availability"]
    list_filter = ["kind", "availability"]
    search_fields = ["name", "episode__title__name"]
