import re

from rest_framework import serializers

from catalog import posters
from catalog.i18n import translated_value
from catalog.serializers import EpisodeSerializer, TitleSerializer

from .models import EpisodeProgress, LibraryEntry, TitleCollection, TitleCollectionItem, TitleNote


COLLECTION_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_COLLECTION_SLUGS = {"new", "edit", "public", "api"}


class LibraryEntrySerializer(serializers.ModelSerializer):
    title = TitleSerializer(read_only=True)

    class Meta:
        model = LibraryEntry
        fields = ["title", "status", "is_favorite", "created_at", "updated_at"]


class LibraryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryEntry
        fields = ["status", "is_favorite"]


class EpisodeProgressSerializer(serializers.ModelSerializer):
    title = TitleSerializer(source="episode.title", read_only=True)
    episode = EpisodeSerializer(read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = EpisodeProgress
        fields = [
            "title",
            "episode",
            "is_watched",
            "watched_seconds",
            "duration_seconds",
            "progress_percent",
            "last_opened_at",
            "watched_at",
        ]


class EpisodePlaybackProgressSerializer(serializers.ModelSerializer):
    """Compact response for frequent player checkpoints."""

    progress_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = EpisodeProgress
        fields = [
            "is_watched",
            "watched_seconds",
            "duration_seconds",
            "progress_percent",
            "last_opened_at",
            "watched_at",
        ]


class EpisodeProgressWriteSerializer(serializers.Serializer):
    is_watched = serializers.BooleanField()


class EpisodePlaybackProgressWriteSerializer(serializers.Serializer):
    max_playback_seconds = 24 * 60 * 60

    watched_seconds = serializers.IntegerField(min_value=0, max_value=max_playback_seconds)
    duration_seconds = serializers.IntegerField(min_value=1, max_value=max_playback_seconds)
    event = serializers.ChoiceField(choices=["progress", "pause", "ended"])

    def validate(self, attrs):
        if attrs["watched_seconds"] > attrs["duration_seconds"]:
            raise serializers.ValidationError(
                {"watched_seconds": "Время просмотра не может превышать длительность эпизода."}
            )
        return attrs


class TitleNoteSerializer(serializers.ModelSerializer):
    title = TitleSerializer(read_only=True)

    class Meta:
        model = TitleNote
        fields = ["title", "body", "created_at", "updated_at"]


class TitleNoteWriteSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000, trim_whitespace=False)

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Заметка не может быть пустой.")
        return value


class RecommendationSerializer(serializers.Serializer):
    title = TitleSerializer(source="*", read_only=True)
    score = serializers.FloatField(read_only=True)
    reasons = serializers.SerializerMethodField()

    def get_reasons(self, obj):
        # The view passes positive-weight genres ordered by weight and already
        # localized; candidates only mention genres that actually matched.
        ordered_names = self.context.get("recommendation_genre_names") or []
        limit = self.context.get("recommendation_genre_limit") or 3
        genre_ids = {genre.id for genre in obj.genres.all()}
        franchise_ids = self.context.get("recommendation_franchise_ids") or set()
        return {
            "genres": [name for genre_id, name in ordered_names if genre_id in genre_ids][:limit],
            "franchise": bool(obj.franchise_id and obj.franchise_id in franchise_ids),
        }


class CollectionItemSerializer(serializers.ModelSerializer):
    title = TitleSerializer(read_only=True)

    class Meta:
        model = TitleCollectionItem
        fields = ["position", "title", "created_at"]


class CollectionPreviewItemSerializer(serializers.ModelSerializer):
    """Poster-only row for collection cards.

    The list endpoint exists to render cards: a name, a count and a few
    posters. Nesting the full ``TitleSerializer`` there meant 50 collections ×
    200 items could serialize 10 000 complete title payloads in one response,
    so previews carry only what a card draws.
    """

    slug = serializers.CharField(source="title.slug", read_only=True)
    name = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()

    class Meta:
        model = TitleCollectionItem
        fields = ["position", "slug", "name", "poster_url"]

    def get_name(self, obj):
        return translated_value(obj.title, "name", self.context)

    def get_poster_url(self, obj):
        return posters.public_poster_reference(obj.title.poster_url)


class PublicCollectionOwnerSerializer(serializers.Serializer):
    public_id = serializers.UUIDField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    profile_is_public = serializers.BooleanField(read_only=True)


class CollectionSummarySerializer(serializers.ModelSerializer):
    """Bounded collection card for the list endpoint.

    ``item_count`` comes from an annotation and ``preview_items`` from a sliced
    prefetch, so the response size no longer scales with how many titles the
    viewer has collected. ``contains_title`` answers the one membership question
    the title page asks and is present only when the client passes ``?title=``.
    """

    owner = PublicCollectionOwnerSerializer(read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    preview_items = serializers.SerializerMethodField()
    contains_title = serializers.SerializerMethodField()

    class Meta:
        model = TitleCollection
        fields = [
            "owner", "name", "slug", "description", "is_public",
            "item_count", "preview_items", "contains_title", "created_at", "updated_at",
        ]

    def get_preview_items(self, obj):
        items = getattr(obj, "preview_items", [])
        return CollectionPreviewItemSerializer(items, many=True, context=self.context).data

    def get_contains_title(self, obj):
        if not self.context.get("membership_title_slug"):
            return None
        return obj.pk in self.context.get("membership_collection_ids", set())


class CollectionSerializer(serializers.ModelSerializer):
    owner = PublicCollectionOwnerSerializer(read_only=True)
    items = CollectionItemSerializer(many=True, read_only=True)

    class Meta:
        model = TitleCollection
        fields = ["owner", "name", "slug", "description", "is_public", "items", "created_at", "updated_at"]
        read_only_fields = ["owner", "items", "created_at", "updated_at"]

    def validate_slug(self, value):
        if value in RESERVED_COLLECTION_SLUGS or not COLLECTION_SLUG_RE.fullmatch(value):
            raise serializers.ValidationError("Slug должен состоять из строчных ASCII-букв, цифр и дефисов.")
        if self.instance is not None and value != self.instance.slug:
            raise serializers.ValidationError("Slug нельзя изменить после создания.")
        return value


class PublicCollectionSerializer(serializers.ModelSerializer):
    owner = PublicCollectionOwnerSerializer(read_only=True)
    items = CollectionItemSerializer(many=True, read_only=True)

    class Meta:
        model = TitleCollection
        fields = ["owner", "name", "slug", "description", "items", "created_at", "updated_at"]


class CollectionItemCreateSerializer(serializers.Serializer):
    title_slug = serializers.SlugField(max_length=260)
    position = serializers.IntegerField(min_value=0, required=False)


class CollectionItemMoveSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=0)
