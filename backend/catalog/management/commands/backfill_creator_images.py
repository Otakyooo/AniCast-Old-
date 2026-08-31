import time

from django.core.management.base import BaseCommand, CommandError

from catalog.creator_images import CreatorImageError, creator_image
from catalog.models import Creator
from catalog.portraits import set_private_origin


class Command(BaseCommand):
    help = "Backfill creator portrait origins from the catalog provider; local photos are preserved."

    def add_arguments(self, parser):
        parser.add_argument("--title", help="Only creators credited on this title slug")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--pause", type=float, default=0.25)

    def handle(self, *args, **options):
        if options["limit"] < 0 or options["pause"] < 0:
            raise CommandError("--limit and --pause must be non-negative")
        creators = Creator.objects.filter(image_origin_url="").order_by("id")
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
                    updated += int(set_private_origin(creator, image_url))
                else:
                    missing += 1
            if options["pause"]:
                time.sleep(options["pause"])
        self.stdout.write(self.style.SUCCESS(
            f"creator images: updated={updated} missing={missing} failed={failed}"
        ))
