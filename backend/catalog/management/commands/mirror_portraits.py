from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from catalog import portraits, posters
from catalog.models import Character, Creator


class Command(BaseCommand):
    help = "Mirror private portrait origins into AniCast media storage (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Download and persist local portraits")
        parser.add_argument("--title", help="Only people linked to this AniCast title slug")
        parser.add_argument("--kind", choices=("characters", "creators"))
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--workers", type=int, default=8)

    def handle(self, *args, **options):
        if options["limit"] < 0 or not 1 <= options["workers"] <= 16:
            raise CommandError("--limit must be non-negative and --workers must be between 1 and 16")

        work: list[tuple[str, int]] = []
        kinds = (options["kind"],) if options["kind"] else ("characters", "creators")
        for kind in kinds:
            model = Character if kind == "characters" else Creator
            queryset = model.objects.exclude(image_origin_url="").order_by("id")
            if options["title"]:
                relation = "title_links__title__slug" if kind == "characters" else "title_credits__title__slug"
                queryset = queryset.filter(**{relation: options["title"]}).distinct()
            for object_id, image_url in queryset.values_list("id", "image_url").iterator():
                if not posters.stored_tier(image_url):
                    work.append((kind, object_id))

        if options["limit"]:
            work = work[:options["limit"]]
        self.stdout.write(f"portrait mirror candidates: {len(work)}")
        if not options["apply"] or not work:
            return

        def mirror(item: tuple[str, int]) -> bool:
            close_old_connections()
            try:
                kind, object_id = item
                record = portraits.portrait_record(kind, object_id)
                if record is None:
                    return False
                portraits.mirror_record(kind, record)
                return True
            except (OSError, ValueError):
                return False
            finally:
                close_old_connections()

        mirrored = failed = 0
        with ThreadPoolExecutor(max_workers=options["workers"]) as executor:
            futures = [executor.submit(mirror, item) for item in work]
            for completed, future in enumerate(as_completed(futures), start=1):
                if future.result():
                    mirrored += 1
                else:
                    failed += 1
                if completed % 250 == 0:
                    self.stdout.write(f"portrait mirror progress: {completed}/{len(work)}")
        self.stdout.write(self.style.SUCCESS(
            f"portrait mirror complete: mirrored={mirrored} failed={failed}"
        ))
