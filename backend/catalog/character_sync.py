import re
from dataclasses import dataclass

from django.db import transaction
from django.utils.text import slugify

from .management.commands.fetch_shikimori import graphql_post
from .models import Character, CharacterTranslation, Title, TitleCharacter


MAL_ID = re.compile(r"^(\d+)-")


class CharacterSyncError(RuntimeError):
    pass


@dataclass
class CharacterSyncResult:
    title: str
    discovered: int = 0
    created: int = 0
    linked: int = 0


def _slug(character_id: int, name: str) -> str:
    return f"{character_id}-{slugify(name) or 'character'}"[:110]


@transaction.atomic
def sync_title_characters(title: Title) -> CharacterSyncResult:
    match = MAL_ID.match(title.slug)
    if match is None:
        raise ValueError("Title slug does not contain a MyAnimeList id")
    anime_id = int(match.group(1))
    response = graphql_post(
        '{animes(ids:"' + str(anime_id) + '"){characterRoles{rolesEn character{id name russian}}}}'
    )
    anime = (((response.get("data") or {}).get("animes") or [None])[0]) if isinstance(response, dict) else None
    rows = anime.get("characterRoles") if isinstance(anime, dict) else None
    if not isinstance(rows, list):
        raise CharacterSyncError("Shikimori character response schema is invalid")

    result = CharacterSyncResult(title=title.slug, discovered=len(rows))
    for position, row in enumerate(rows):
        raw = row.get("character") if isinstance(row, dict) else None
        if not isinstance(raw, dict):
            continue
        try:
            character_id = int(raw.get("id"))
        except (TypeError, ValueError):
            continue
        english = " ".join(str(raw.get("name") or "").split())[:200]
        russian = " ".join(str(raw.get("russian") or "").split())[:200]
        if not english and not russian:
            continue
        slug = _slug(character_id, english or russian)
        character, created = Character.objects.get_or_create(
            slug=slug,
            defaults={"name": russian or english},
        )
        result.created += int(created)
        for language, name in (("en", english), ("ru", russian)):
            if name:
                CharacterTranslation.objects.update_or_create(
                    character=character,
                    language=language,
                    defaults={"name": name},
                )
        roles = row.get("rolesEn") if isinstance(row.get("rolesEn"), list) else []
        role = "protagonist" if any(str(value).casefold() == "main" for value in roles) else "supporting"
        _, linked = TitleCharacter.objects.update_or_create(
            title=title,
            character=character,
            defaults={"role": role, "sort_order": position},
        )
        result.linked += int(linked)
    return result
