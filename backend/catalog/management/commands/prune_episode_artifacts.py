"""Remove episode rows that the absolute-numbering import left above a work's run.

The metadata import once read `absoluteEpisodeNumber` as the episode number, so a
season continuing a franchise's numbering gained a second row for episodes it
already had. Those rows sit above the work's local episode count and are what
still shows up as duplicate episode names.

A row is deleted only when it is provably an artifact of another row:

* it carries no related records at all beyond translations. A row with a player,
  progress or a delivery is not disposable — it holds something the catalogue
  would lose, and the provider's later packs give those rows URLs the canonical
  row does not have, so it is kept and reported rather than deleted;
* it is named after one of the work's own local episodes. A row named something
  else may be a genuine special that belongs there, so it is kept too.

Decisions are per row, not per title: one row that must be kept does not make its
neighbours unsafe, and leaving them is just incomplete rather than inconsistent.
The work's highest local episode can have its correct name sitting on a row about
to be deleted; that name and its translations move down first, and only from a row
that is itself being deleted, so a name is never lost.

Dry-run by default; nothing is written without `--apply`.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.management.commands.repair_episode_numbering import _identity_key
from catalog.models import Episode, EpisodeTranslation, Title


def _local_names(payload: dict) -> dict[int, str]:
    return {
        int(key): (row.get("title") or {}).get("en", "")
        for key, row in payload.get("episodes", {}).items()
        if str(key).isdigit() and isinstance(row, dict)
    }


def _attached(episode: Episode) -> dict[str, int]:
    counts: dict[str, int] = {}
    for relation in episode._meta.related_objects:
        model = relation.related_model
        if not isinstance(model, type) or model is EpisodeTranslation:
            continue
        accessor = relation.get_accessor_name()
        if accessor is None:
            continue
        count = getattr(episode, accessor).count()
        if count:
            counts[model.__name__] = count
    return counts


class Command(BaseCommand):
    help = "Delete the episode rows an absolute-numbering import left above the local run."

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

        local_names = _local_names(payload)
        if not local_names:
            raise CommandError("Mapping has no local episodes")
        local_max = max(local_names)
        known_names = {_identity_key(name) for name in local_names.values() if name}

        with transaction.atomic():
            title = Title.objects.select_for_update().get(slug=slug)
            episodes = {e.number: e for e in Episode.objects.select_for_update().filter(title=title)}
            beyond = sorted(number for number in episodes if number > local_max)
            if not beyond:
                self.stdout.write(f"DRY-RUN: nothing above local {local_max}; pruned=0 kept=0")
                return

            deletable: list[int] = []
            for number in beyond:
                attached = _attached(episodes[number])
                if attached:
                    self.stdout.write(
                        f"keeping {number}: carries {sorted(attached)}; needs re-pointing"
                    )
                    continue
                if _identity_key(episodes[number].name) not in known_names:
                    self.stdout.write(
                        f"keeping {number}: {episodes[number].name!r} is not named after a local episode"
                    )
                    continue
                deletable.append(number)

            local_row = episodes.get(local_max)
            if local_row is None:
                raise CommandError(f"Local episode {local_max} is missing")
            wanted = _identity_key(local_names[local_max])
            donor_number = None
            if _identity_key(local_row.name) != wanted:
                donors = [n for n in deletable if _identity_key(episodes[n].name) == wanted]
                if len(donors) > 1:
                    raise CommandError(
                        f"Expected one row carrying the name of local {local_max}, found {len(donors)}"
                    )
                if donors:
                    donor_number = donors[0]
                    self.stdout.write(
                        f"name {episodes[donor_number].name!r} moves from {donor_number} to {local_max}"
                    )
                else:
                    self.stdout.write(
                        f"local {local_max} keeps {local_row.name!r}: the row holding its name is kept"
                    )

            if options["apply"]:
                if donor_number is not None:
                    donor = episodes[donor_number]
                    for translation in donor.translations.all():
                        dest, _ = EpisodeTranslation.objects.get_or_create(
                            episode=local_row, language=translation.language
                        )
                        if not dest.name:
                            dest.name = translation.name
                        if not dest.synopsis:
                            dest.synopsis = translation.synopsis
                        dest.save()
                    local_row.name = donor.name
                    local_row.save(update_fields=["name"])
                for number in deletable:
                    self.stdout.write(f"deleting {number}")
                    episodes[number].delete()
            else:
                transaction.set_rollback(True)

        self.stdout.write(
            f"{'APPLIED' if options['apply'] else 'DRY-RUN'}: pruned={len(deletable)} "
            f"kept={len(beyond) - len(deletable)}"
        )
