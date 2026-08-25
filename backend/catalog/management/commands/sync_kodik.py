from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.kodik import KodikAPIError
from catalog.kodik_sync import sync_title
from catalog.models import Title


class Command(BaseCommand):
    help = "Synchronize Kodik players, schedule metadata and credits. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("title_slug", nargs="?")
        parser.add_argument("--all", action="store_true", dest="all_titles")
        parser.add_argument("--season", type=int, default=1)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--activate", action="store_true")
        parser.add_argument("--rights-reference", default="")

    def handle(self, *args, **options):
        if bool(options["title_slug"]) == bool(options["all_titles"]):
            raise CommandError("Укажите title_slug или --all")
        if options["activate"] and not options["apply"]:
            raise CommandError("--activate требует --apply")
        if options["activate"] and not options["rights_reference"].strip():
            raise CommandError("--activate требует --rights-reference")
        if not 1 <= options["limit"] <= 100:
            raise CommandError("--limit должен быть от 1 до 100")

        titles = Title.objects.order_by("id")
        if options["title_slug"]:
            titles = titles.filter(slug=options["title_slug"])
        if not titles.exists():
            raise CommandError("Тайтл не найден")

        totals = {key: 0 for key in ("titles", "failed", "discovered", "persisted", "created_episodes", "scheduled", "credits", "stale", "skipped")}
        for title in titles.iterator():
            try:
                if options["apply"]:
                    result = sync_title(
                        title,
                        season=options["season"],
                        limit=options["limit"],
                        activate=options["activate"],
                        rights_reference=options["rights_reference"],
                    )
                else:
                    # Roll back each title independently instead of holding one
                    # library-wide transaction open for the whole batch.
                    with transaction.atomic():
                        result = sync_title(
                            title,
                            season=options["season"],
                            limit=options["limit"],
                            activate=False,
                            rights_reference="",
                        )
                        transaction.set_rollback(True)
            except (KodikAPIError, ValueError) as error:
                totals["failed"] += 1
                self.stderr.write(f"SKIP {title.slug}: {error}")
                continue
            totals["titles"] += 1
            for key in totals:
                if hasattr(result, key):
                    totals[key] += getattr(result, key)

        mode = "APPLIED" if options["apply"] else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(f"{mode}: " + ", ".join(f"{key}={value}" for key, value in totals.items())))
