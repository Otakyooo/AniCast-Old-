import re

from rest_framework import serializers

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

    class Meta:
        model = EpisodeProgress
        fields = ["title", "episode", "is_watched", "last_opened_at", "watched_at"]


class EpisodeProgressWriteSerializer(serializers.Serializer):
    is_watched = serializers.BooleanField()


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
    score = serializers.IntegerField(read_only=True)


class CollectionItemSerializer(serializers.ModelSerializer):
    title = TitleSerializer(read_only=True)

    class Meta:
        model = TitleCollectionItem
        fields = ["position", "title", "created_at"]


class PublicCollectionOwnerSerializer(serializers.Serializer):
    public_id = serializers.UUIDField(read_only=True)
    display_name = serializers.CharField(read_only=True)


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
