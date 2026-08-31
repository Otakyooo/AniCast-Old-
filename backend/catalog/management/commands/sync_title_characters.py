from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.character_sync import CharacterSyncError, sync_title_characters
from catalog.models import Title


class Command(BaseCommand):
    help = "Fill complete title character lists from the catalog provider. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("title_slug", nargs="?")
        parser.add_argument("--all", action="store_true", dest="all_titles")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if bool(options["title_slug"]) == bool(options["all_titles"]):
            raise CommandError("Укажите title_slug или --all")
        titles = Title.objects.order_by("id")
        if options["title_slug"]:
            titles = titles.filter(slug=options["title_slug"])
        if options["limit"]:
            titles = titles[: max(1, options["limit"])]
        totals = {"titles": 0, "failed": 0, "discovered": 0, "created": 0, "linked": 0}
        for title in titles:
            try:
                with transaction.atomic():
                    result = sync_title_characters(title)
                    if not options["apply"]:
                        transaction.set_rollback(True)
            except (CharacterSyncError, OSError, ValueError) as error:
                totals["failed"] += 1
                self.stderr.write(f"SKIP {title.slug}: {error}")
                continue
            totals["titles"] += 1
            for key in ("discovered", "created", "linked"):
                totals[key] += getattr(result, key)
        mode = "APPLIED" if options["apply"] else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(f"{mode}: " + ", ".join(f"{key}={value}" for key, value in totals.items())))
