from rest_framework import serializers

from .i18n import translated_value
from .models import Character, MediaAsset, Episode, Franchise, Genre, Source, SourceReport, Title, TitleCharacter

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

    class Meta:
        model = Source
        fields = ["id", "name", "kind", "availability", "availability_reason", "is_available", "playback_available"]

    def get_playback_available(self, obj):
        from .playback import playback_available

        return playback_available(obj)


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
        fields = ["id", "number", "name", "synopsis", "air_date", "sources"]


class FranchiseSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_description(self, obj):
        return translated_value(obj, "description", self.context)

    class Meta:
        model = Franchise
        fields = ["name", "slug", "description"]


class TitleSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    franchise = FranchiseSerializer(read_only=True)
    name = serializers.SerializerMethodField()
    synopsis = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_synopsis(self, obj):
        return translated_value(obj, "synopsis", self.context)

    class Meta:
        model = Title
        fields = [
            "name", "slug", "original_name", "synopsis", "title_type", "status",
            "year", "poster_url", "genres", "franchise",
        ]


class TitleDetailSerializer(TitleSerializer):
    episodes = serializers.SerializerMethodField()
    episodes_count = serializers.SerializerMethodField()

    class Meta(TitleSerializer.Meta):
        fields = TitleSerializer.Meta.fields + ["episodes", "episodes_count"]

    def get_episodes(self, obj):
        from .playback import playback_sources_prefetch

        episodes = (
            Episode.objects.filter(title=obj)
            .prefetch_related("translations", playback_sources_prefetch())
            .order_by("number")
        )
        paginator = self.context.get("episodes_paginator")
        if paginator is None:
            return EpisodeSerializer(episodes, many=True, context=self.context).data
        page = paginator.paginate_queryset(episodes, self.context["request"])
        return EpisodeSerializer(page, many=True, context=self.context).data

    def get_episodes_count(self, obj):
        count = getattr(obj, "episodes_count", None)
        return count if count is not None else obj.episodes.count()


class ScheduleTitleSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    class Meta:
        model = Title
        fields = ["name", "slug", "poster_url", "title_type", "status"]


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
        fields = ["id", "number", "name", "synopsis", "air_date", "title"]


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

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_description(self, obj):
        return translated_value(obj, "description", self.context)

    class Meta:
        model = Franchise
        fields = ["name", "slug", "description", "title_count"]


class FranchiseTitleSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    name = serializers.SerializerMethodField()
    synopsis = serializers.SerializerMethodField()

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_synopsis(self, obj):
        return translated_value(obj, "synopsis", self.context)

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

    def get_name(self, obj):
        return translated_value(obj, "name", self.context)

    def get_description(self, obj):
        return translated_value(obj, "description", self.context)

    class Meta:
        model = Character
        fields = ["name", "slug", "original_name", "description", "image_url", "title_count"]


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

    def get_caption(self, obj):
        return translated_value(obj, "caption", self.context)

    class Meta:
        model = MediaAsset
        fields = ["id", "kind", "url", "thumbnail_url", "caption", "credit", "title", "character"]


class EpisodeDetailSerializer(EpisodeSerializer):
    title = ScheduleTitleSerializer(read_only=True)

    class Meta(EpisodeSerializer.Meta):
        fields = EpisodeSerializer.Meta.fields + ["title"]
