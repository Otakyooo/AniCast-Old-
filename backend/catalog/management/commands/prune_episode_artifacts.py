"""Repair the episode rows an absolute-numbering import left above a work's run.

The metadata import once read `absoluteEpisodeNumber` as the episode number, so a
season continuing a franchise's numbering gained a second row for episodes it
already had. Those rows sit above the work's local episode count and are what
still shows up as duplicate episode names.

A row is repaired only when it is provably an artifact of another row, and the
repair keeps everything the row held:

* every row above the local run must be named after one of the work's own local
  episodes. A row named something the local run does not know may be a genuine
  special — One Punch Man's rows 13..18 are its six OVAs, and two of them kept
  their own titles — so the whole title is refused rather than guessed at;
* a row carrying progress or a delivery is kept: that is someone's data and
  belongs to a re-pointing migration, not this one;
* the row's players are moved onto the local row it duplicates, skipping URLs
  already there, and only then is the row deleted. Dropping them instead would
  lose player links the canonical row does not have, which is a real loss even
  though the translator itself is already offered.

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
from catalog.models import Episode, EpisodeTranslation, Source, Title


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
        if not isinstance(model, type) or model in (EpisodeTranslation, Source):
            continue
        accessor = relation.get_accessor_name()
        if accessor is None:
            continue
        count = getattr(episode, accessor).count()
        if count:
            counts[model.__name__] = count
    return counts


class Command(BaseCommand):
    help = "Repair the episode rows an absolute-numbering import left above the local run."

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
                self.stdout.write(f"DRY-RUN: nothing above local {local_max}; repaired=0 kept=0")
                return

            unknown = [
                number
                for number in beyond
                if episodes[number].name and _identity_key(episodes[number].name) not in known_names
            ]
            if unknown:
                raise CommandError(
                    f"Episode(s) {unknown} are named something the local run does not know, so "
                    "they may be genuine specials; nothing was changed"
                )

            # Resolve every target before mutating anything: the local maximum's
            # own name may be about to change. A row carrying the local maximum's
            # provider name belongs to the local maximum itself, even though no
            # local row is named that yet -- that row is the one whose name has to
            # move down, so looking it up by name among the local rows would miss
            # it and strand the name.
            local_row = episodes.get(local_max)
            if local_row is None:
                raise CommandError(f"Local episode {local_max} is missing")
            wanted = _identity_key(local_names[local_max])
            canonical: dict[int, Episode | None] = {}
            by_name: dict[str, Episode] = {}
            for number, episode in episodes.items():
                if number <= local_max and episode.name:
                    by_name.setdefault(_identity_key(episode.name), episode)
            for number in beyond:
                name_key = _identity_key(episodes[number].name)
                canonical[number] = (
                    local_row if name_key and name_key == wanted else by_name.get(name_key)
                )

            repaired: list[int] = []
            for number in beyond:
                attached = _attached(episodes[number])
                if attached:
                    self.stdout.write(
                        f"keeping {number}: carries {sorted(attached)}; needs a data migration"
                    )
                    continue
                if canonical[number] is None:
                    self.stdout.write(f"keeping {number}: no local row it could be a copy of")
                    continue
                repaired.append(number)

            donor_number = None
            if _identity_key(local_row.name) != wanted:
                donors = [n for n in repaired if _identity_key(episodes[n].name) == wanted]
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
                for number in repaired:
                    row = episodes[number]
                    target = canonical[number]
                    if target is None:  # pragma: no cover - guarded above
                        continue
                    existing = {url for url in Source.objects.filter(episode=target).values_list("url", flat=True)}
                    moved = 0
                    for source in Source.objects.filter(episode=row):
                        if source.url in existing:
                            continue
                        source.episode = target
                        source.save(update_fields=["episode"])
                        existing.add(source.url)
                        moved += 1
                    self.stdout.write(f"deleting {number} (moved {moved} player(s) to {target.number})")
                    row.delete()
            else:
                transaction.set_rollback(True)

        self.stdout.write(
            f"{'APPLIED' if options['apply'] else 'DRY-RUN'}: repaired={len(repaired)} "
            f"kept={len(beyond) - len(repaired)}"
        )
