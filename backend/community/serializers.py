from rest_framework import serializers

from catalog.serializers import ScheduleTitleSerializer

from .models import TitleRating, TitleReview


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TitleRating
        fields = ["value", "created_at", "updated_at"]


class RatingWriteSerializer(serializers.Serializer):
    value = serializers.IntegerField(min_value=1, max_value=10)


class PublicReviewSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    title = ScheduleTitleSerializer(read_only=True)

    def get_author_name(self, obj):
        return obj.user.display_name or f"AniCast #{obj.user_id}"

    class Meta:
        model = TitleReview
        fields = ["id", "title", "author_name", "body", "contains_spoilers", "published_at", "updated_at"]


class PrivateReviewSerializer(PublicReviewSerializer):
    class Meta(PublicReviewSerializer.Meta):
        fields = PublicReviewSerializer.Meta.fields + ["status", "moderation_note"]


class ReviewWriteSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=20, max_length=5000, trim_whitespace=True)
    contains_spoilers = serializers.BooleanField(default=False)
