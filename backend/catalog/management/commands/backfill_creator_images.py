import time

from django.core.management.base import BaseCommand, CommandError

from catalog.creator_images import CreatorImageError, creator_image
from catalog.models import Creator


class Command(BaseCommand):
    help = "Backfill real creator photos from Shikimori; existing photos are preserved."

    def add_arguments(self, parser):
        parser.add_argument("--title", help="Only creators credited on this title slug")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--pause", type=float, default=0.25)

    def handle(self, *args, **options):
        if options["limit"] < 0 or options["pause"] < 0:
            raise CommandError("--limit and --pause must be non-negative")
        creators = Creator.objects.filter(image_url="").order_by("id")
        if options["title"]:
            creators = creators.filter(title_credits__title__slug=options["title"]).distinct()
        if options["limit"]:
            creators = creators[:options["limit"]]

        updated = missing = failed = 0
        for creator in creators.iterator():
            try:
                image_url = creator_image(creator.name)
            except CreatorImageError:
                failed += 1
            else:
                if image_url:
                    creator.image_url = image_url
                    creator.save(update_fields=["image_url"])
                    updated += 1
                else:
                    missing += 1
            if options["pause"]:
                time.sleep(options["pause"])
        self.stdout.write(self.style.SUCCESS(
            f"creator images: updated={updated} missing={missing} failed={failed}"
        ))
