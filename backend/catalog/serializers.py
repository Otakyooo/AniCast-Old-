from rest_framework import serializers

from . import portraits, posters
from .i18n import request_language, translated_value
from .models import Character, Creator, MediaAsset, Episode, Franchise, Genre, Source, SourceReport, Title, TitleCharacter


def title_payload_prefetch(prefix: str = "") -> tuple[str, ...]:
    """Related names :class:`TitleSerializer` reads for every row.

    ``translated_value`` calls ``instance.translations.all()``, so an
    unprefetched title costs one query per localized field and one more per
    genre. Callers that nest ``TitleSerializer`` under another model pass the
    relation prefix, e.g. ``title_payload_prefetch("title")``.
    """
    base = f"{prefix}__" if prefix else ""
    return (
        f"{base}translations",
        f"{base}franchise__translations",
        f"{base}genres",
        f"{base}genres__translations",
    )


def episode_payload_prefetch(prefix: str = "") -> tuple[str, ...]:
    """Related names the episode serializers read for every row."""
    base = f"{prefix}__" if prefix else ""
    return (f"{base}translations",)


def schedule_title_payload_prefetch(prefix: str = "") -> tuple[str, ...]:
    """Related names :class:`ScheduleTitleSerializer` reads for every row.

    The compact payload carries only the localized name, so it needs the
    translations but not genres or the franchise.
    """
    base = f"{prefix}__" if prefix else ""
    return (f"{base}translations",)


class GenreSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    class Meta:
        model = Genre
        fields = ["name", "slug"]


class SourceSerializer(serializers.ModelSerializer):
    is_available = serializers.BooleanField(read_only=True)
    playback_available = serializers.SerializerMethodField()
    playback_mode = serializers.SerializerMethodField()
    provider_name = serializers.CharField(source="provider.name", read_only=True, default="")
    provider_variant_id = serializers.SerializerMethodField()
    selection_key = serializers.SerializerMethodField()

    class Meta:
        model = Source
        fields = [
            "id", "name", "kind", "provider_name", "provider_variant_id", "selection_key", "availability",
            "availability_reason", "is_available", "playback_available", "playback_mode",
        ]

    def get_playback_available(self, obj):
        from .playback import playback_available

        return playback_available(obj)

    def get_playback_mode(self, obj):
        from .playback import playback_adapters

        if obj.provider is None or playback_adapters.get(obj.provider.playback_adapter) is None:
            return None
        return obj.provider.playback_adapter

    def get_selection_key(self, obj):
        from .playback import source_selection_key

        return source_selection_key(obj)

    def get_provider_variant_id(self, obj):
        from .playback import source_provider_variant_id

        return source_provider_variant_id(obj)


class EpisodeSerializer(serializers.ModelSerializer):
    sources = SourceSerializer(many=True, read_only=True)
    name = serializers.SerializerMethodField()
    synopsis = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_synopsis(self, obj):
        return translated_value(obj, "synopsis", self.context)

    class Meta:
        model = Episode
        fields = ["id", "number", "name", "synopsis", "air_date", "air_at", "sources"]


class EpisodeSummarySerializer(serializers.ModelSerializer):
    """Episode row for catalog navigation, without playback source payloads."""

    name = serializers.SerializerMethodField()
    synopsis = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_synopsis(self, obj):
        return translated_value(obj, "synopsis", self.context)

    class Meta:
        model = Episode
        fields = ["id", "number", "name", "synopsis", "air_date", "air_at"]


class FranchiseRefSerializer(serializers.ModelSerializer):
    """Compact franchise reference embedded in title payloads. The long
    localized description belongs to the franchise endpoints; carrying it on
    every catalog card only inflates list responses."""

    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    class Meta:
        model = Franchise
        fields = ["name", "slug"]


class TitleSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    franchise = FranchiseRefSerializer(read_only=True)
    name = serializers.SerializerMethodField()
    synopsis = serializers.SerializerMethodField()
    rating_average = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    localized_names = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()

    def get_poster_url(self, obj):
        return posters.public_poster_reference(obj.poster_url)

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_synopsis(self, obj):
        return translated_value(obj, "synopsis", self.context)

    def get_rating_average(self, obj):
        # Present only when the queryset annotated the aggregate; unannotated
        # callers stay at null instead of triggering per-object queries.
        average = getattr(obj, "rating_avg", None)
        return round(average, 1) if average is not None else None

    def get_rating_count(self, obj):
        return getattr(obj, "rating_count", None)

    def get_localized_names(self, obj):
        """Stable RU/EN/JA names independent from the request locale.

        The localized ``name`` field remains backwards compatible, while title
        pages and search suggestions can now show exactly which aliases are
        available. Empty languages are omitted; equal official spellings stay
        present under their own language labels.
        """
        translations = {item.language: item.name.strip() for item in obj.translations.all() if item.name.strip()}
        candidates = (
            ("ru", translations.get("ru", "")),
            ("en", translations.get("en", "") or obj.name.strip()),
            ("ja", translations.get("ja", "") or obj.original_name.strip()),
        )
        return {language: value for language, value in candidates if value}

    class Meta:
        model = Title
        fields = [
            "name", "slug", "original_name", "synopsis", "title_type", "status",
            "year", "poster_url", "genres", "franchise",
            "rating_average", "rating_count", "localized_names",
        ]


class TitleDetailSerializer(TitleSerializer):
    episodes = serializers.SerializerMethodField()
    episodes_count = serializers.SerializerMethodField()
    characters = serializers.SerializerMethodField()
    credits = serializers.SerializerMethodField()
    related_titles = serializers.SerializerMethodField()
    characters_count = serializers.SerializerMethodField()

    class Meta(TitleSerializer.Meta):
        fields = TitleSerializer.Meta.fields + ["duration_minutes", "episodes", "episodes_count", "characters", "characters_count", "credits", "related_titles"]

    def get_episodes(self, obj):
        from .playback import playback_sources_prefetch

        episodes = Episode.objects.filter(title=obj).prefetch_related("translations").order_by("number")
        include_sources = self.context.get("include_episode_sources", True)
        if include_sources:
            episodes = episodes.prefetch_related(playback_sources_prefetch())
        paginator = self.context.get("episodes_paginator")
        # The detail view always supplies a paginator; the fallback keeps other
        # callers (tests, management code) from silently serializing 1000+ rows.
        page = episodes if paginator is None else paginator.paginate_queryset(episodes, self.context["request"])
        serializer = EpisodeSerializer if include_sources else EpisodeSummarySerializer
        return serializer(page, many=True, context=self.context).data

    def get_episodes_count(self, obj):
        count = getattr(obj, "episodes_count", None)
        return count if count is not None else obj.episodes.count()

    def get_characters(self, obj):
        links = TitleCharacter.objects.filter(title=obj).select_related("character").prefetch_related(
            "character__translations"
        )
        paginator = self.context.get("characters_paginator")
        if paginator is not None:
            links = paginator.paginate_queryset(links, self.context["request"])
            # Reuse the count already calculated by Django's paginator instead
            # of issuing the same COUNT query again for characters_count.
            self.context["characters_count"] = paginator.page.paginator.count
        return TitleCharacterSerializer(links, many=True, context=self.context).data

    def get_characters_count(self, obj):
        count = self.context.get("characters_count")
        return count if count is not None else obj.character_links.count()

    def get_credits(self, obj):
        language = request_language(self.context)
        return [
            {
                "role": credit.role,
                "role_label": (
                    credit.role_en if language == "en" else credit.role_ru
                ) or credit.role.replace("_", " ").title(),
                "sort_order": credit.sort_order,
                "creator": {
                    "name": credit.creator.name,
                    "slug": credit.creator.slug,
                    "image_url": portraits.public_portrait_url(
                        "creators",
                        credit.creator.pk,
                        credit.creator.image_url,
                        credit.creator.image_origin_url,
                    ),
                },
            }
            for credit in obj.credits.all()
        ]

    def get_related_titles(self, obj):
        if obj.franchise_id is None:
            return []
        prefetched = getattr(obj.franchise, "related_titles_prefetched", None)
        if prefetched is None:
            prefetched = list(obj.franchise.titles.prefetch_related("translations"))
        related = sorted(
            (title for title in prefetched if title.pk != obj.pk),
            key=lambda title: (title.year is None, title.year or 0, title.name, title.id),
        )
        return [
            {
                "name": translated_value(title, "name", self.context),
                "slug": title.slug,
                "poster_url": posters.public_poster_reference(title.poster_url),
                "title_type": title.title_type,
                "status": title.status,
                "year": title.year,
            }
            for title in related
        ]


class CreatorDetailSerializer(serializers.ModelSerializer):
    title_credits = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Creator
        fields = ["name", "slug", "image_url", "title_credits"]

    def get_image_url(self, obj):
        return portraits.public_portrait_url(
            "creators", obj.pk, obj.image_url, obj.image_origin_url
        )

    def get_title_credits(self, obj):
        language = request_language(self.context)
        return [
            {
                "role": credit.role,
                "role_label": (
                    credit.role_en if language == "en" else credit.role_ru
                ) or credit.role.replace("_", " ").title(),
                "sort_order": credit.sort_order,
                "title": TitleSerializer(credit.title, context=self.context).data,
            }
            for credit in obj.title_credits.all()
        ]


class ScheduleTitleSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_poster_url(self, obj):
        return posters.public_poster_reference(obj.poster_url)

    class Meta:
        model = Title
        fields = ["name", "slug", "poster_url", "title_type", "status", "year"]


class ScheduleEpisodeSerializer(serializers.ModelSerializer):
    title = ScheduleTitleSerializer(read_only=True)
    name = serializers.SerializerMethodField()
    synopsis = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_synopsis(self, obj):
        return translated_value(obj, "synopsis", self.context)

    class Meta:
        model = Episode
        fields = ["id", "number", "name", "synopsis", "air_date", "air_at", "title"]


class SourceReportSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)
    title_slug = serializers.CharField(source="source.episode.title.slug", read_only=True)
    episode_number = serializers.IntegerField(source="source.episode.number", read_only=True)

    class Meta:
        model = SourceReport
        fields = [
            "id", "source", "source_name", "title_slug", "episode_number",
            "reason", "message", "status", "resolution_note", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "resolution_note"]

    def validate(self, attrs):
        request = self.context["request"]
        if attrs["reason"] == SourceReport.Reason.OTHER and not attrs.get("message", "").strip():
            raise serializers.ValidationError({"message": "Опишите проблему."})
        if SourceReport.objects.filter(
            source=attrs["source"],
            reporter=request.user,
            reason=attrs["reason"],
            status__in=[SourceReport.Status.NEW, SourceReport.Status.REVIEWING],
        ).exists():
            raise serializers.ValidationError({"reason": "Такая жалоба уже находится на рассмотрении."})
        return attrs


class FranchiseSummarySerializer(serializers.ModelSerializer):
    title_count = serializers.IntegerField(read_only=True)
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    poster_urls = serializers.SerializerMethodField()
    year_from = serializers.SerializerMethodField()
    year_to = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_description(self, obj):
        return translated_value(obj, "description", self.context)

    def _titles(self, obj):
        return list(obj.titles.all())

    def get_poster_urls(self, obj):
        return [
            public_url
            for title in self._titles(obj)
            if (public_url := posters.public_poster_reference(title.poster_url))
        ][:3]

    def get_year_from(self, obj):
        years = [title.year for title in self._titles(obj) if title.year]
        return min(years) if years else None

    def get_year_to(self, obj):
        years = [title.year for title in self._titles(obj) if title.year]
        return max(years) if years else None

    class Meta:
        model = Franchise
        fields = ["name", "slug", "description", "title_count", "poster_urls", "year_from", "year_to"]


class FranchiseTitleSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    name = serializers.SerializerMethodField()
    synopsis = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_synopsis(self, obj):
        return translated_value(obj, "synopsis", self.context)

    def get_poster_url(self, obj):
        return posters.public_poster_reference(obj.poster_url)

    class Meta:
        model = Title
        fields = ["name", "slug", "original_name", "synopsis", "title_type", "status", "year", "poster_url", "genres"]


class FranchiseDetailSerializer(FranchiseSummarySerializer):
    titles = FranchiseTitleSerializer(many=True, read_only=True)

    class Meta(FranchiseSummarySerializer.Meta):
        fields = FranchiseSummarySerializer.Meta.fields + ["titles"]


class CharacterSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    title_count = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_description(self, obj):
        return translated_value(obj, "description", self.context)

    def get_image_url(self, obj):
        return portraits.public_portrait_url(
            "characters", obj.pk, obj.image_url, obj.image_origin_url
        )

    class Meta:
        model = Character
        fields = ["name", "slug", "original_name", "description", "image_url", "title_count"]


class CastCharacterSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_image_url(self, obj):
        return portraits.public_portrait_url(
            "characters", obj.pk, obj.image_url, obj.image_origin_url
        )

    class Meta:
        model = Character
        fields = ["name", "slug", "original_name", "image_url"]


class TitleCharacterSerializer(serializers.ModelSerializer):
    """Cast entry on the title page. Deliberately narrower than the character list
    payload so the nested list needs no per-character aggregate query."""

    character = CastCharacterSerializer(read_only=True)

    class Meta:
        model = TitleCharacter
        fields = ["character", "role", "sort_order"]


class CharacterTitleLinkSerializer(serializers.ModelSerializer):
    title = FranchiseTitleSerializer(read_only=True)

    class Meta:
        model = TitleCharacter
        fields = ["title", "role", "sort_order"]


class CharacterDetailSerializer(CharacterSummarySerializer):
    title_links = CharacterTitleLinkSerializer(many=True, read_only=True)

    class Meta(CharacterSummarySerializer.Meta):
        fields = CharacterSummarySerializer.Meta.fields + ["title_links"]


class MediaAssetSerializer(serializers.ModelSerializer):
    caption = serializers.SerializerMethodField()
    title = ScheduleTitleSerializer(read_only=True)
    character = CharacterSummarySerializer(read_only=True)
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    def get_caption(self, obj):
        return translated_value(obj, "caption", self.context)

    def get_url(self, obj):
        return "" if portraits.is_allowed_origin(obj.url) else obj.url

    def get_thumbnail_url(self, obj):
        return "" if portraits.is_allowed_origin(obj.thumbnail_url) else obj.thumbnail_url

    class Meta:
        model = MediaAsset
        fields = ["id", "kind", "url", "thumbnail_url", "caption", "credit", "title", "character"]


class EpisodeDetailSerializer(EpisodeSerializer):
    title = ScheduleTitleSerializer(read_only=True)

    class Meta(EpisodeSerializer.Meta):
        fields = EpisodeSerializer.Meta.fields + ["title"]


class ShelfEpisodeSerializer(serializers.ModelSerializer):
    """Episode reference without sources, for shelves that only need to link to
    the episode page. Skipping sources keeps playback authorization out of a
    list response that never offers playback itself."""

    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    class Meta:
        model = Episode
        fields = ["id", "number", "name", "air_date", "air_at"]


class GenreOptionSerializer(serializers.Serializer):
    """Compact genre entry for the catalog filter bar, localized like every
    other public payload via the request language."""

    slug = serializers.CharField()
    name = serializers.SerializerMethodField()
    titles_count = serializers.IntegerField()

    def get_name(self, obj) -> str:
        return translated_value(obj, "name", self.context)
