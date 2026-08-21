from rest_framework import serializers

from catalog.serializers import TitleSerializer

from .models import LibraryEntry


class LibraryEntrySerializer(serializers.ModelSerializer):
    title = TitleSerializer(read_only=True)

    class Meta:
        model = LibraryEntry
        fields = ["title", "status", "is_favorite", "created_at", "updated_at"]


class LibraryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryEntry
        fields = ["status", "is_favorite"]
