from django.conf import settings
from django.db import models

from catalog.models import Title


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
