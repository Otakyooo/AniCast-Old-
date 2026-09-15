import re
import json
import subprocess
from dataclasses import dataclass

from django.db import transaction
from django.utils.text import slugify

from . import providers
from .models import Character, CharacterTranslation, Title, TitleCharacter
from .portraits import set_private_origin


MAL_ID = re.compile(r"^(\d+)-")


class CharacterSyncError(RuntimeError):
    pass


@dataclass
class CharacterSyncResult:
    title: str
    discovered: int = 0
    created: int = 0
    linked: int = 0


def _character_roles(anime_id: int) -> list[dict]:
    query = (
        '{animes(ids:"' + str(anime_id) + '"){characterRoles{rolesEn character{'
        'id name russian poster{originalUrl main2xUrl}}}}}'
    )
    try:
        result = subprocess.run(
            [
                "curl", "-sSL", "--fail", "--max-time", "45", "--max-filesize", "20971520",
                "-H", "User-Agent: AniCast/1.0 (catalog metadata import)",
                "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"query": query}),
                providers.graphql_url(),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        response = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise CharacterSyncError("Catalog character request failed") from error
    anime = (((response.get("data") or {}).get("animes") or [None])[0]) if isinstance(response, dict) else None
    rows = anime.get("characterRoles") if isinstance(anime, dict) else None
    if not isinstance(rows, list):
        raise CharacterSyncError("Catalog character response schema is invalid")
    return rows


def _slug(character_id: int, name: str) -> str:
    return f"{character_id}-{slugify(name) or 'character'}"[:110]


@transaction.atomic
def sync_title_characters(title: Title) -> CharacterSyncResult:
    match = MAL_ID.match(title.slug)
    if match is None:
        raise ValueError("Title slug does not contain a MyAnimeList id")
    anime_id = int(match.group(1))
    rows = _character_roles(anime_id)

    result = CharacterSyncResult(title=title.slug, discovered=len(rows))
    for position, row in enumerate(rows):
        raw = row.get("character") if isinstance(row, dict) else None
        if not isinstance(raw, dict):
            continue
        raw_character_id = raw.get("id")
        if not isinstance(raw_character_id, (str, int)) or isinstance(raw_character_id, bool):
            continue
        try:
            character_id = int(raw_character_id)
        except ValueError:
            continue
        english = " ".join(str(raw.get("name") or "").split())[:200]
        russian = " ".join(str(raw.get("russian") or "").split())[:200]
        if not english and not russian:
            continue
        slug = _slug(character_id, english or russian)
        character, created = Character.objects.get_or_create(
            slug=slug,
            defaults={"name": russian or english, "image_url": "", "image_origin_url": ""},
        )
        result.created += int(created)
        raw_poster = raw.get("poster")
        poster: dict = raw_poster if isinstance(raw_poster, dict) else {}
        image_url = str(poster.get("originalUrl") or poster.get("main2xUrl") or "")
        if image_url and "missing_" not in image_url:
            set_private_origin(character, image_url)
        for language, name in (("en", english), ("ru", russian)):
            if name:
                CharacterTranslation.objects.update_or_create(
                    character=character,
                    language=language,
                    defaults={"name": name},
                )
        raw_roles = row.get("rolesEn")
        roles: list = raw_roles if isinstance(raw_roles, list) else []
        role = "protagonist" if any(str(value).casefold() == "main" for value in roles) else "supporting"
        _, linked = TitleCharacter.objects.update_or_create(
            title=title,
            character=character,
            defaults={"role": role, "sort_order": position},
        )
        result.linked += int(linked)
    return result
