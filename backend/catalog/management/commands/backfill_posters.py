from django.core.management.base import BaseCommand
from django.db.models import Q

from catalog.management.commands import fetch_shikimori
from catalog.models import Title


class Command(BaseCommand):
    help = (
        "Replace missing or low-resolution Shikimori posters with larger "
        "MyAnimeList artwork (dry-run by default, --apply to write)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write poster_url changes")
        parser.add_argument("--limit", type=int, default=0, help="Process at most N titles")

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        limit = max(0, int(options["limit"]))
        queryset = (
            Title.objects.filter(Q(poster_url="") | Q(poster_url__contains="shikimori"))
            .order_by("id")
        )
        if limit:
            queryset = queryset[:limit]
        candidates = replaced = kept = 0
        for title in queryset.iterator():
            candidates += 1
            prefix = title.slug.split("-", 1)[0]
            if not prefix.isdigit():
                self.stdout.write(self.style.WARNING(f"skip    {title.slug}: slug has no numeric id"))
                continue
            poster = fetch_shikimori.mal_poster({"id": int(prefix)})
            if not poster or "shikimori" in poster:
                kept += 1
                self.stdout.write(f"keep    {title.slug}: MAL artwork unavailable")
                continue
            if poster == title.poster_url:
                kept += 1
                self.stdout.write(f"keep    {title.slug}: already up to date")
                continue
            marker = "replace" if apply_changes else "plan    "
            self.stdout.write(
                f"{marker} {title.slug}: {title.poster_url or '(empty)'} -> {poster}"
            )
            if apply_changes:
                replaced += 1
                Title.objects.filter(pk=title.pk).update(poster_url=poster)
        summary = f"{candidates} candidates, {replaced} replaced, {kept} kept"
        if apply_changes:
            self.stdout.write(self.style.SUCCESS(f"applied: {summary}"))
        else:
            self.stdout.write(self.style.NOTICE(f"dry-run: {summary}; rerun with --apply"))
