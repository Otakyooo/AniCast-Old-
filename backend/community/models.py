from django.conf import settings
from django.db import models
from django.db.models import Q

from catalog.models import Title


class TitleRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="title_ratings", on_delete=models.CASCADE)
    title = models.ForeignKey(Title, related_name="ratings", on_delete=models.CASCADE)
    value = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "title"], name="unique_user_title_rating"),
            models.CheckConstraint(condition=Q(value__gte=1, value__lte=10), name="rating_between_1_and_10"),
        ]


class TitleReview(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На модерации"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="title_reviews", on_delete=models.CASCADE)
    title = models.ForeignKey(Title, related_name="reviews", on_delete=models.CASCADE)
    body = models.TextField(max_length=5000)
    contains_spoilers = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    moderation_note = models.CharField(max_length=500, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="moderated_title_reviews", null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "title"], name="unique_user_title_review")]
        indexes = [models.Index(fields=["status", "published_at"])]


class ProfileFollow(models.Model):
    """A private subscription edge between two opt-in public profiles."""

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="profile_following",
        on_delete=models.CASCADE,
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="profile_followers",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["follower", "following"], name="unique_profile_follow"),
            models.CheckConstraint(
                condition=~Q(follower=models.F("following")),
                name="prevent_self_profile_follow",
            ),
        ]
        indexes = [models.Index(fields=["following", "created_at"])]

    def __str__(self) -> str:
        return f"{self.follower_id} follows {self.following_id}"
