"""Classify a work's specials and name them from the providers that own them.

Kodik keeps a work's specials in its own season zero, exactly as TVDB and TMDB do,
and ani.zip names them under keys `S1`..`Sn`. Neither alone is enough: Kodik knows
which of our stored players belong to a special but not what it is called, and the
mapping knows the names but not which row holds which one.

Together they are conclusive. Every player URL we stored carries the id of the pack
it came from, Kodik's season-zero episode list maps each of those ids to a special
number, and the mapping names that number. So a row is identified by its own
players and named from the mapping -- nothing is renamed unless both agree, and a
row whose players are not all from season zero is left alone.

The row is also marked season 0, so it stops sharing the regular episode numbers.
Dry-run by default.
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
    """Map each stored pack id to the special number Kodik files it under.

    Season zero is the provider's own word for "this is a special", so a player
    whose pack appears there is a special player. Conflicting answers are refused
    rather than resolved by picking one.
    """
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
        try:
            seria_to_special = _kodik_special_seria(int(mal_id))
        except KodikAPIError as error:
            raise CommandError(f"Kodik lookup failed: {error}") from error
        if not seria_to_special:
            raise CommandError("Kodik reports no season-zero episodes for this title")

        identified: list[tuple[Episode, int]] = []
        with transaction.atomic():
            title = Title.objects.select_for_update().get(slug=slug)
            episodes = list(Episode.objects.select_for_update().filter(title=title).order_by("number"))
            for episode in episodes:
                seria = set()
                for url in Source.objects.filter(episode=episode).values_list("url", flat=True):
                    match = SERIA.search(url or "")
                    if match:
                        seria.add(match.group(1))
                if not seria:
                    continue
                numbers = {seria_to_special.get(value) for value in seria}
                if None in numbers or len(numbers) != 1:
                    # Mixed or unknown packs: not provably one special, so left alone.
                    continue
                identified.append((episode, numbers.pop()))

            for episode, number in identified:
                wanted = specials.get(number)
                if wanted is None:
                    raise CommandError(f"Mapping has no special {number}")
                self.stdout.write(f"{episode.number}: special {number} -> {wanted}")

            if options["apply"]:
                for episode, number in identified:
                    wanted = specials[number]
                    if "en" in wanted and episode.name != wanted["en"]:
                        episode.name = wanted["en"]
                    episode.season_number = 0
                    episode.save(update_fields=["name", "season_number"])
                    # The provider's name is the authority for every language it
                    # supplies, so a missing translation is filled in rather than
                    # left to fall back to the base name.
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
            f"{'APPLIED' if options['apply'] else 'DRY-RUN'}: specials={len(identified)}"
        )
