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
    author_public_id = serializers.SerializerMethodField()
    title = ScheduleTitleSerializer(read_only=True)

    def get_author_name(self, obj):
        # An empty display name stays empty; the client renders its own localized
        # placeholder. The previous fallback embedded the internal primary key,
        # which exposed registration order and a rough user count in a public
        # payload — and it did so precisely for the reviewers whose public_id is
        # deliberately withheld below.
        return obj.user.display_name

    def get_author_public_id(self, obj):
        return str(obj.user.public_id) if obj.user.profile_is_public else None

    class Meta:
        model = TitleReview
        fields = [
            "id", "title", "author_name", "author_public_id", "body",
            "contains_spoilers", "published_at", "updated_at",
        ]


class PrivateReviewSerializer(PublicReviewSerializer):
    class Meta(PublicReviewSerializer.Meta):
        fields = PublicReviewSerializer.Meta.fields + ["status", "moderation_note"]


class ReviewWriteSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=20, max_length=5000, trim_whitespace=True)
    contains_spoilers = serializers.BooleanField(default=False)
