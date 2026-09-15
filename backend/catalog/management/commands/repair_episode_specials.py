"""Move a legacy special row's players onto the special the mapping numbers it under.

Kodik numbers a work's specials in its own season zero and the mapping numbers them
`S1`..`Sn`; the two are offset by a per-work amount. The rows the old import left
behind are numbered by neither -- One Punch Man's six OVAs sit at 13..18 because
they collided with regular episode numbers -- so renaming a row in place would put
one special's title on another special's players.

The rows are therefore relocated: each identified row's players move to the row the
mapping numbers that special, and the row they came from is left as whatever the
mapping says it is. The offset is fixed by an anchor -- the highest row whose own
title is one of the mapping's special titles and which is not named after a regular
episode -- so nothing moves on a guess.

A row is identified when at least one of its packs is filed in Kodik's season zero
and those packs agree on one number. Translators disagree about which season an
extra belongs to -- Brotherhood's STEPonee counts its four OVAs as episodes 65..68
of a longer season while MiraiDUB files them in season zero -- so requiring every
pack to be there would find nothing, and requiring the season-zero packs to agree is
the real test.

Dry-run by default.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.kodik import KodikAPIError, search_by_shikimori
from catalog.models import Episode, Source, Title

SERIA = re.compile(r"/seria/(\d+)/")
LANGUAGES = ("en", "ja")


def _identity_key(value: object) -> str:
    return "".join(c for c in str(value or "").casefold() if c.isalnum())


def _mapping_specials(payload: dict) -> dict[int, dict[str, str]]:
    """The provider's specials, keyed `S1`..`Sn`, by number."""
    specials: dict[int, dict[str, str]] = {}
    for key, row in (payload.get("episodes") or {}).items():
        key = str(key)
        if not key.startswith("S") or not key[1:].isdigit() or not isinstance(row, dict):
            continue
        title = row.get("title")
        if not isinstance(title, dict):
            continue
        values = {lang: title[lang] for lang in LANGUAGES if isinstance(title.get(lang), str) and title[lang]}
        if values:
            specials[int(key[1:])] = values
    return specials


def _kodik_special_seria(mal_id: int) -> dict[str, int]:
    """Map each stored pack id to the special number Kodik files it under."""
    result = search_by_shikimori(mal_id, with_material_data=True)
    mapping: dict[str, int] = {}
    for row in result.results:
        seasons = row.get("seasons") or {}
        if not isinstance(seasons, dict):
            continue
        zero = seasons.get(0) or seasons.get("0")
        episodes = (zero or {}).get("episodes") if isinstance(zero, dict) else None
        if not isinstance(episodes, dict):
            continue
        for number, episode in episodes.items():
            link = (episode or {}).get("link") if isinstance(episode, dict) else None
            match = SERIA.search(link or "")
            if match is None:
                continue
            seria, special_number = match.group(1), int(number)
            if mapping.setdefault(seria, special_number) != special_number:
                raise CommandError(f"Pack {seria} is both special {mapping[seria]} and {special_number}")
    return mapping


class Command(BaseCommand):
    help = "Move legacy special rows' players onto the special the mapping numbers them under."

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
        mal_id = slug.split("-", 1)[0]
        if str(payload.get("mappings", {}).get("mal_id")) != mal_id:
            raise CommandError("Mapping MAL id does not match title")

        specials = _mapping_specials(payload)
        if not specials:
            raise CommandError("Mapping has no specials")
        local_names = {
            _identity_key((row.get("title") or {}).get("en", ""))
            for key, row in (payload.get("episodes") or {}).items()
            if str(key).isdigit() and isinstance(row, dict)
        }
        by_title = {_identity_key(values.get("en")): number for number, values in specials.items()}
        try:
            seria_to_special = _kodik_special_seria(int(mal_id))
        except KodikAPIError as error:
            raise CommandError(f"Kodik lookup failed: {error}") from error
        if not seria_to_special:
            raise CommandError("Kodik reports no season-zero episodes for this title")

        rows: list[tuple[Episode, int]] = []
        with transaction.atomic():
            title = Title.objects.select_for_update().get(slug=slug)
            for episode in Episode.objects.select_for_update().filter(title=title).order_by("number"):
                packs = set()
                for url in Source.objects.filter(episode=episode).values_list("url", flat=True):
                    match = SERIA.search(url or "")
                    if match:
                        packs.add(match.group(1))
                if not packs:
                    continue
                mapped = {seria_to_special[pack] for pack in packs if pack in seria_to_special}
                if not mapped or len(mapped) != 1:
                    continue
                rows.append((episode, mapped.pop()))

            if not rows:
                self.stdout.write("DRY-RUN: relocated=0")
                return

            anchors = [
                (number, by_title[_identity_key(episode.name)])
                for episode, number in rows
                if _identity_key(episode.name) in by_title
                and _identity_key(episode.name) not in local_names
            ]
            offset = 0
            if anchors:
                highest, special_number = max(anchors)
                offset = special_number - highest
                self.stdout.write(f"anchor: special {highest} is S{special_number} -> offset {offset:+d}")

            moves: list[tuple[Episode, int]] = []
            for episode, number in rows:
                target = number + offset
                if target < 1 or target not in specials:
                    raise CommandError(f"Special {number} maps to S{target}, which the mapping does not have")
                if episode.number != target or episode.season_number != 0:
                    moves.append((episode, target))

            if options["apply"]:
                for episode, target in moves:
                    target_row = Episode.objects.filter(
                        title=title, season_number=0, number=target
                    ).first()
                    if target_row is None:
                        target_row = Episode.objects.create(
                            title=title, number=target, season_number=0
                        )
                    existing = {
                        url
                        for url in Source.objects.filter(episode=target_row).values_list("url", flat=True)
                    }
                    moved = 0
                    for source in Source.objects.filter(episode=episode):
                        if source.url in existing:
                            continue
                        source.episode = target_row
                        source.save(update_fields=["episode"])
                        existing.add(source.url)
                        moved += 1
                    self.stdout.write(f"{episode.number} -> special {target}: moved {moved} player(s)")
                    episode.delete()
            else:
                transaction.set_rollback(True)

        self.stdout.write(f"{'APPLIED' if options['apply'] else 'DRY-RUN'}: relocated={len(moves)}")
