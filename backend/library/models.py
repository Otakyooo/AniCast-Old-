from django.conf import settings
from django.db import models

from catalog.models import Episode, Title


class LibraryEntry(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Запланировано"
        WATCHING = "watching", "Смотрю"
        COMPLETED = "completed", "Просмотрено"
        ON_HOLD = "on_hold", "Отложено"
        DROPPED = "dropped", "Брошено"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="library_entries", on_delete=models.CASCADE)
    title = models.ForeignKey(Title, related_name="library_entries", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "title"], name="unique_user_library_title")]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "is_favorite"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} / {self.title}"


class EpisodeProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="episode_progress", on_delete=models.CASCADE)
    episode = models.ForeignKey(Episode, related_name="user_progress", on_delete=models.CASCADE)
    is_watched = models.BooleanField(default=False)
    last_opened_at = models.DateTimeField()
    watched_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_opened_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "episode"], name="unique_user_episode_progress")]
        indexes = [models.Index(fields=["user", "last_opened_at"])]

    def __str__(self) -> str:
        return f"{self.user} / {self.episode}"


class TitleNote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="title_notes", on_delete=models.CASCADE)
    title = models.ForeignKey(Title, related_name="user_notes", on_delete=models.CASCADE)
    body = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "title"], name="unique_user_title_note")]
        indexes = [models.Index(fields=["user", "updated_at"])]

    def __str__(self) -> str:
        return f"{self.user} / {self.title}"


class TitleCollection(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="title_collections", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80)
    description = models.CharField(max_length=500, blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["owner", "slug"], name="unique_owner_collection_slug")]

    def __str__(self) -> str:
        return f"{self.owner} / {self.name}"


class TitleCollectionItem(models.Model):
    collection = models.ForeignKey(TitleCollection, related_name="items", on_delete=models.CASCADE)
    title = models.ForeignKey(Title, related_name="collection_items", on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["collection", "title"], name="unique_collection_title"),
            models.UniqueConstraint(fields=["collection", "position"], name="unique_collection_position"),
        ]

    def __str__(self) -> str:
        return f"{self.collection} / {self.title}"
