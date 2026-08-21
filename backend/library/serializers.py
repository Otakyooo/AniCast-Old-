from rest_framework import serializers

from catalog.serializers import EpisodeSerializer, TitleSerializer

from .models import EpisodeProgress, LibraryEntry


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
