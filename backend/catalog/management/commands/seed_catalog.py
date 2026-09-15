from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalog.models import (
    Episode,
    EpisodeTranslation,
    Franchise,
    FranchiseTranslation,
    Genre,
    GenreTranslation,
    Provider,
    Source,
    Title,
    TitleTranslation,
)


GENRES = [
    ("Action", "Экшен", "action"),
    ("Adventure", "Приключения", "adventure"),
    ("Comedy", "Комедия", "comedy"),
    ("Drama", "Драма", "drama"),
    ("Fantasy", "Фэнтези", "fantasy"),
]


class Command(BaseCommand):
    help = "Create the small deterministic catalog used for local development."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not settings.USE_SQLITE:
            raise CommandError(
                "seed_catalog is a development fixture and is blocked outside local development"
            )
        genres = {}
        for english_name, russian_name, slug in GENRES:
            genre = Genre.objects.update_or_create(slug=slug, defaults={"name": english_name})[0]
            GenreTranslation.objects.update_or_create(genre=genre, language="en", defaults={"name": english_name})
            GenreTranslation.objects.update_or_create(genre=genre, language="ru", defaults={"name": russian_name})
            genres[slug] = genre
        franchise, _ = Franchise.objects.update_or_create(
            slug="demo-franchise", defaults={"name": "Demo Franchise", "description": "Seed catalog franchise.", "sort_order": 0}
        )
        FranchiseTranslation.objects.update_or_create(
            franchise=franchise, language="en", defaults={"name": "Demo Franchise", "description": "Seed catalog franchise."}
        )
        FranchiseTranslation.objects.update_or_create(
            franchise=franchise, language="ru", defaults={"name": "Демо-франшиза", "description": "Тестовая франшиза каталога."}
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
        TitleTranslation.objects.update_or_create(
            title=title, language="en", defaults={"name": "Demo Title", "synopsis": "A deterministic sample title for development."}
        )
        TitleTranslation.objects.update_or_create(
            title=title, language="ru", defaults={"name": "Демо-тайтл", "synopsis": "Детерминированный пример тайтла для разработки."}
        )
        title.genres.set([genres["action"], genres["adventure"]])
        episode, _ = Episode.objects.update_or_create(
            title=title, number=1, defaults={"name": "First Episode", "synopsis": "The story begins."}
        )
        EpisodeTranslation.objects.update_or_create(
            episode=episode, language="en", defaults={"name": "First Episode", "synopsis": "The story begins."}
        )
        EpisodeTranslation.objects.update_or_create(
            episode=episode, language="ru", defaults={"name": "Первый эпизод", "synopsis": "История начинается."}
        )
        # Upcoming episodes exercise the schedule statuses locally: one released,
        # one within the hour and one on a later day, all with an explicit moment.
        today = timezone.localdate()
        current_zone = timezone.get_current_timezone()
        upcoming = [
            (2, "Second Episode", "Второй эпизод", timezone.now() - timedelta(hours=3)),
            (3, "Third Episode", "Третий эпизод", timezone.now() + timedelta(minutes=25)),
            (
                4,
                "Fourth Episode",
                "Четвёртый эпизод",
                timezone.make_aware(
                    datetime.combine(today + timedelta(days=2), time(21, 30)), current_zone
                ),
            ),
        ]
        for number, english_name, russian_name, moment in upcoming:
            extra, _ = Episode.objects.update_or_create(
                title=title,
                number=number,
                season_number=1,
                defaults={"name": english_name, "air_at": moment},
            )
            EpisodeTranslation.objects.update_or_create(
                episode=extra, language="en", defaults={"name": english_name}
            )
            EpisodeTranslation.objects.update_or_create(
                episode=extra, language="ru", defaults={"name": russian_name}
            )
        provider, _ = Provider.objects.update_or_create(
            slug="demo-provider",
            defaults={"name": "Demo Provider", "allowed_hosts": ["example.invalid"], "is_enabled": False},
        )
        Source.objects.update_or_create(
            episode=episode,
            name="Demo Provider",
            kind="sub",
            external_id="",
            defaults={"provider": provider, "url": "https://example.invalid/demo-title/1", "availability": "available", "availability_reason": "Demo source only."},
        )
        self.stdout.write(self.style.SUCCESS("Catalog seed completed."))
