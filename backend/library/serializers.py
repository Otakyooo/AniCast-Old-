from rest_framework import serializers

from catalog.serializers import EpisodeSerializer, TitleSerializer

from .models import EpisodeProgress, LibraryEntry, TitleNote


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
