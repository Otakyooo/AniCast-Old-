"""Repair verified metadata-only duplicates for one work; dry-run by default."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Episode, EpisodeTranslation, Title


class Command(BaseCommand):
    help = "Merge empty absolute-number duplicates using a reviewed ani.zip mapping file."

    def add_arguments(self, parser):
        parser.add_argument("title_slug")
        parser.add_argument("mapping_file")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["mapping_file"])
        if path.stat().st_size > 20 * 1024 * 1024:
            raise CommandError("Mapping exceeds 20 MiB")
        payload = json.loads(path.read_text(encoding="utf-8"))
        slug = options["title_slug"]
        if str(payload.get("mappings", {}).get("mal_id")) != slug.split("-", 1)[0]:
            raise CommandError("Mapping MAL id does not match title")
        pairs = []
        for local, row in payload.get("episodes", {}).items():
            if not str(local).isdigit() or not isinstance(row, dict):
                continue
            absolute = row.get("absoluteEpisodeNumber")
            if type(absolute) is int and int(local) > 0 and absolute > 0 and absolute != int(local):
                pairs.append((int(local), absolute, row.get("title", {}).get("en")))
        if len(pairs) > 100 or len({p[1] for p in pairs}) != len(pairs):
            raise CommandError("Ambiguous or oversized mapping")
        if {p[0] for p in pairs} & {p[1] for p in pairs}:
            raise CommandError("Overlapping number ranges require manual review")

        merged = 0
        with transaction.atomic():
            title = Title.objects.select_for_update().get(slug=slug)
            episodes = {e.number: e for e in Episode.objects.select_for_update().filter(title=title)}
            for local, absolute, name in pairs:
                source = episodes.get(absolute)
                if source is None:
                    continue  # Already repaired: idempotent.
                target = episodes.get(local)
                if not target or not name or source.name != name or target.name != name:
                    raise CommandError(f"Unconfirmed identity: {absolute} -> {local}")
                # Never delete sources, progress, delivery history or future
                # related models. PostgreSQL row locks also block new FK links.
                for relation in Episode._meta.related_objects:
                    if relation.related_model is EpisodeTranslation:
                        continue
                    if getattr(source, relation.get_accessor_name()).exists():
                        raise CommandError(f"Episode {absolute} has related records; no changes applied")
                for field in ("synopsis", "air_date", "air_at"):
                    old, new = getattr(source, field), getattr(target, field)
                    if old and new and old != new:
                        raise CommandError(f"Conflicting {field}: {absolute} -> {local}")
                    if old and not new:
                        setattr(target, field, old)
                target.save()
                for translation in source.translations.all():
                    dest, _ = EpisodeTranslation.objects.get_or_create(episode=target, language=translation.language)
                    for field in ("name", "synopsis"):
                        old, new = getattr(translation, field), getattr(dest, field)
                        if old and new and old != new:
                            raise CommandError(f"Conflicting translation: {absolute} -> {local}")
                        if old and not new:
                            setattr(dest, field, old)
                    dest.save()
                source.delete()
                merged += 1
                self.stdout.write(f"{absolute} -> {local}")
            if not options["apply"]:
                transaction.set_rollback(True)
        self.stdout.write(f"{'APPLIED' if options['apply'] else 'DRY-RUN'}: merged={merged}")
