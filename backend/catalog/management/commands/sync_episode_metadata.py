from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.episode_metadata import EpisodeMetadataError, sync_title_episode_metadata
from catalog.models import Title


class Command(BaseCommand):
    help = "Fill episode names and confirmed air dates from Jikan/MAL. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("title_slug", nargs="?")
        parser.add_argument("--all", action="store_true", dest="all_titles")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--max-pages", type=int, default=25)
        parser.add_argument("--fallback-first", action="store_true", help="Use the one-request ani.zip/TVDB mapping before Jikan")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if bool(options["title_slug"]) == bool(options["all_titles"]):
            raise CommandError("Укажите title_slug или --all")
        if options["limit"] < 0:
            raise CommandError("--limit не может быть отрицательным")

        titles = Title.objects.order_by("id")
        if options["title_slug"]:
            titles = titles.filter(slug=options["title_slug"])
        if options["limit"]:
            titles = titles[: options["limit"]]
        titles = list(titles)
        if not titles:
            raise CommandError("Тайтл не найден")

        totals = {key: 0 for key in ("titles", "failed", "pages", "episodes", "created", "named", "dated")}
        for title in titles:
            try:
                with transaction.atomic():
                    result = sync_title_episode_metadata(
                        title,
                        max_pages=options["max_pages"],
                        fallback_first=options["fallback_first"],
                    )
                    if not options["apply"]:
                        transaction.set_rollback(True)
            except (EpisodeMetadataError, ValueError) as error:
                totals["failed"] += 1
                self.stderr.write(f"SKIP {title.slug}: {error}")
                continue
            totals["titles"] += 1
            for key in ("pages", "episodes", "created", "named", "dated"):
                totals[key] += getattr(result, key)

        mode = "APPLIED" if options["apply"] else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(f"{mode}: " + ", ".join(f"{key}={value}" for key, value in totals.items())))
