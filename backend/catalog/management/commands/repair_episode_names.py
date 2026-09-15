"""Put back the episode names the absolute-numbering import wrote at wrong numbers.

The import took `absoluteEpisodeNumber` as the episode number and wrote each
episode's *name* under it. On Cowboy Bebop that field is not a franchise-absolute
number at all -- the mapping's key 1 carries `episodeNumber: 14` with
`absoluteEpisodeNumber: 4`, and key 13 carries `absoluteEpisodeNumber: 1` -- so
names landed scattered across the run while the player links, which Kodik
numbered by the row's own number, stayed correct. The rows are right; their
labels are not.

The mapping's keys *are* the MAL episode numbers and its `title` carries `en` and
`ja`, which is exactly what the catalog stores, so the names can be restored from
it. Two guards keep this from becoming a rewrite of editorial text:

* a name is only replaced when the current one is provably a misplaced copy --
  it equals another episode's provider title. Text that merely differs is left
  alone, which is why spelling drift like "Envoy From the East" against the
  provider's "The Envoy from the East" is not touched;
* a name matching no provider title at all is refused outright, because that is
  text we did not write.

Refusing is per title, so a title is never left half-renamed. Dry-run by default.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.management.commands.repair_episode_numbering import _identity_key
from catalog.models import Episode, Title

# Languages the provider supplies and the catalog stores per episode.
LANGUAGES = ("en", "ja")


def _provider_titles(payload: dict) -> dict[int, dict[str, str]]:
    titles: dict[int, dict[str, str]] = {}
    for key, row in payload.get("episodes", {}).items():
        if not str(key).isdigit() or not isinstance(row, dict):
            continue
        title = row.get("title")
        if not isinstance(title, dict):
            continue
        values = {lang: title[lang] for lang in LANGUAGES if isinstance(title.get(lang), str) and title[lang]}
        if values:
            titles[int(key)] = values
    return titles


class Command(BaseCommand):
    help = "Restore episode names written at the wrong number, using the provider mapping."

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

        provider = _provider_titles(payload)
        if not provider:
            raise CommandError("Mapping has no titled episodes")
        known = {
            language: {_identity_key(values[language]) for values in provider.values() if language in values}
            for language in LANGUAGES
        }

        renames: list[tuple[Episode, str, dict[str, str]]] = []
        with transaction.atomic():
            title = Title.objects.select_for_update().get(slug=slug)
            episodes = list(Episode.objects.select_for_update().filter(title=title).order_by("number"))
            for episode in episodes:
                wanted = provider.get(episode.number)
                if not wanted:
                    continue
                changes: dict[str, str] = {}
                if "en" in wanted and _identity_key(episode.name) != _identity_key(wanted["en"]):
                    if _identity_key(episode.name) not in known["en"]:
                        raise CommandError(
                            f"Episode {episode.number} name {episode.name!r} is not a provider title; "
                            "refusing to overwrite text we did not write"
                        )
                    changes["en"] = wanted["en"]
                for translation in episode.translations.all():
                    language = translation.language
                    if language not in wanted or language not in known:
                        continue
                    if _identity_key(translation.name) == _identity_key(wanted[language]):
                        continue
                    if _identity_key(translation.name) not in known[language]:
                        raise CommandError(
                            f"Episode {episode.number} {language} name {translation.name!r} is not a "
                            "provider title; refusing to overwrite text we did not write"
                        )
                    changes[language] = wanted[language]
                if changes:
                    renames.append((episode, changes["en"] if "en" in changes else "", changes))

            for episode, new_name, changes in renames:
                self.stdout.write(f"{episode.number}: {episode.name!r} -> {changes}")
            if options["apply"]:
                for episode, new_name, changes in renames:
                    if new_name:
                        episode.name = new_name
                        episode.save(update_fields=["name"])
                    for translation in episode.translations.all():
                        if translation.language in changes:
                            translation.name = changes[translation.language]
                            translation.save(update_fields=["name"])
            else:
                transaction.set_rollback(True)

        self.stdout.write(
            f"{'APPLIED' if options['apply'] else 'DRY-RUN'}: renamed={len(renames)}"
        )
