"""Classify a work's specials and name them from the providers that own them.

Kodik keeps a work's specials in its own season zero, exactly as TVDB and TMDB do,
and ani.zip names them under keys `S1`..`Sn`. Neither alone is enough: Kodik knows
which of our stored players belong to a special but not what it is called, and the
mapping knows the names but not which row holds which one.

The two numberings are not the same list. Kodik's season zero holds the episodes
its translators published as specials, while the mapping's `S` keys also cover
shorts and recaps, so the two line up only up to an offset that differs per work:
One Punch Man's six match `S1`..`S6`, while Brotherhood's four OVAs are `S2`..`S5`
because its `S1` is a recap and `S6` onwards are shorts.

The offset is fixed by an anchor rather than assumed. A row whose own title is one
of the mapping's special titles, and which is not named after a regular episode,
identifies itself; the highest such row is used, because a corrupted title always
came from a collision with a regular episode's number and the last special is the
one that could not collide. Everything else follows from the offset, and the result
is refused unless the titles come out distinct.

A row is only marked as a special when at least one of its packs is in season zero,
which is the provider's own word for it, and only renamed when every one of its
packs is. Dry-run by default.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.kodik import KodikAPIError, search_by_shikimori
from catalog.models import Episode, EpisodeTranslation, Source, Title

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
    help = "Mark a work's specials as season 0 and name them from the provider mapping."

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
                # Only the packs filed in season zero count. Translators disagree
                # about which season an extra belongs to -- Brotherhood's STEPonee
                # counts the four OVAs as episodes 65..68 of a longer season while
                # MiraiDUB files them in season zero -- so requiring every pack to
                # be there would find nothing, and requiring none to disagree is
                # the real test.
                mapped = {seria_to_special[pack] for pack in packs if pack in seria_to_special}
                if not mapped or len(mapped) != 1:
                    continue
                rows.append((episode, mapped.pop()))

            if not rows:
                self.stdout.write("DRY-RUN: specials=0")
                return

            # Anchor: the highest special whose current title is one of the
            # mapping's, so the offset between the two numberings is fixed by
            # evidence rather than assumed.
            anchors = [
                (number, by_title[_identity_key(episode.name)])
                for episode, number in rows
                if _identity_key(episode.name) in by_title
                and _identity_key(episode.name) not in local_names
            ]
            offset = 0
            named = False
            if anchors:
                highest, special_number = max(anchors)
                offset = special_number - highest
                named = True
                self.stdout.write(f"anchor: special {highest} is S{special_number} -> offset {offset:+d}")

            planned: list[tuple[Episode, int, dict[str, str]]] = []
            for episode, number in rows:
                wanted = specials.get(number + offset) if named else None
                planned.append((episode, number, wanted or {}))
            names = [values.get("en") for _, _, values in planned if values.get("en")]
            if len(names) != len(set(names)):
                raise CommandError("The offset produces duplicate titles; refusing")

            for episode, number, wanted in planned:
                self.stdout.write(f"{episode.number}: special {number} -> {wanted.get('en') or '(kept)'}")

            if options["apply"]:
                for episode, number, wanted in planned:
                    changed = ["season_number"]
                    episode.season_number = 0
                    if wanted.get("en") and episode.name != wanted["en"]:
                        episode.name = wanted["en"]
                        changed.append("name")
                    episode.save(update_fields=changed)
                    for language, value in wanted.items():
                        translation, _ = EpisodeTranslation.objects.get_or_create(
                            episode=episode, language=language
                        )
                        if translation.name != value:
                            translation.name = value
                            translation.save(update_fields=["name"])
            else:
                transaction.set_rollback(True)

        self.stdout.write(
            f"{'APPLIED' if options['apply'] else 'DRY-RUN'}: specials={len(planned)} "
            f"named={sum(1 for _, _, values in planned if values)}"
        )
