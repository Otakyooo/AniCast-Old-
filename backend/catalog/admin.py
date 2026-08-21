from django.contrib import admin

from .models import Episode, Franchise, Genre, Source, Title


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
