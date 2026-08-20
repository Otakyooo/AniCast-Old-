from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Episode, Franchise, Genre, Source, Title


GENRES = [
    ("Action", "action"),
    ("Adventure", "adventure"),
    ("Comedy", "comedy"),
    ("Drama", "drama"),
    ("Fantasy", "fantasy"),
]


class Command(BaseCommand):
    help = "Create the small deterministic catalog used for local development."

    @transaction.atomic
    def handle(self, *args, **options):
        genres = {slug: Genre.objects.update_or_create(slug=slug, defaults={"name": name})[0] for name, slug in GENRES}
        franchise, _ = Franchise.objects.update_or_create(
            slug="demo-franchise", defaults={"name": "Demo Franchise", "description": "Seed catalog franchise.", "sort_order": 0}
        )
        title, _ = Title.objects.update_or_create(
            slug="demo-title",
            defaults={
                "name": "Demo Title",
                "original_name": "デモタイトル",
                "synopsis": "A deterministic sample title for development.",
                "title_type": "anime",
                "status": "ongoing",
                "year": 2026,
                "franchise": franchise,
            },
        )
        title.genres.set([genres["action"], genres["adventure"]])
        episode, _ = Episode.objects.update_or_create(
            title=title, number=1, defaults={"name": "First Episode", "synopsis": "The story begins."}
        )
        Source.objects.update_or_create(
            episode=episode,
            name="Demo Provider",
            kind="sub",
            defaults={"url": "https://example.invalid/demo-title/1", "availability": "available", "availability_reason": "Demo source only."},
        )
        self.stdout.write(self.style.SUCCESS("Catalog seed completed."))
