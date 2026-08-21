from rest_framework import serializers

from .models import Episode, Franchise, Genre, Source, Title


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ["name", "slug"]


class SourceSerializer(serializers.ModelSerializer):
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Source
        fields = ["name", "kind", "url", "availability", "availability_reason", "is_available"]


class EpisodeSerializer(serializers.ModelSerializer):
    sources = SourceSerializer(many=True, read_only=True)

    class Meta:
        model = Episode
        fields = ["id", "number", "name", "synopsis", "air_date", "sources"]


class FranchiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Franchise
        fields = ["name", "slug", "description"]


class TitleSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    franchise = FranchiseSerializer(read_only=True)

    class Meta:
        model = Title
        fields = [
            "name", "slug", "original_name", "synopsis", "title_type", "status",
            "year", "poster_url", "genres", "franchise",
        ]


class TitleDetailSerializer(TitleSerializer):
    episodes = EpisodeSerializer(many=True, read_only=True)

    class Meta(TitleSerializer.Meta):
        fields = TitleSerializer.Meta.fields + ["episodes"]


class ScheduleTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Title
        fields = ["name", "slug", "poster_url", "title_type", "status"]


class ScheduleEpisodeSerializer(serializers.ModelSerializer):
    title = ScheduleTitleSerializer(read_only=True)

    class Meta:
        model = Episode
        fields = ["id", "number", "name", "synopsis", "air_date", "title"]
