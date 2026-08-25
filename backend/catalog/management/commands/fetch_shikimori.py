import json
import re
import subprocess
import time
import urllib.request

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

API_BASE = "https://shikimori.io/api"
JIKAN_BASE = "https://api.jikan.moe/v4"
USER_AGENT = "AniCast/1.0 (catalog metadata import)"
REQUEST_PAUSE_SECONDS = 0.7

BB_CODE_TAGS = re.compile(r"\[/?[^\]]+\]")

KIND_MAP = {
    "tv": "anime",
    "tv_13": "anime",
    "tv_24": "anime",
    "tv_48": "anime",
    "tv_short": "anime",
    "movie": "movie",
    "ova": "ova",
    "ona": "ova",
    "special": "special",
    "music": "special",
}

STATUS_MAP = {
    "ongoing": "ongoing",
    "released": "finished",
    "anons": "planned",
    "discontinued": "finished",
}


def api_get(path: str) -> object:
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def jikan_get(path: str) -> dict:
    # Jikan's edge answers 504 to the python TLS fingerprint while curl
    # works reliably, so shell out for these requests.
    result = subprocess.run(
        ["curl", "-sSL", "--fail", "--max-time", "20", f"{JIKAN_BASE}{path}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def jikan_anime_images(anime_id: int) -> dict:
    """The anime ``images.jpg`` mapping after bounded retries.

    Single owner of the Jikan retry and pause policy: both the import
    fetcher and the poster refresh pipeline consume this helper so their
    rate-limit behaviour cannot drift apart.
    """
    for _ in range(3):
        try:
            time.sleep(REQUEST_PAUSE_SECONDS + 0.4)
            payload = jikan_get(f"/anime/{anime_id}")
            return (((payload.get("data") or {}).get("images") or {}).get("jpg") or {})
        except Exception:
            time.sleep(3)
    return {}


def mal_poster(entry: dict) -> str:
    """Shikimori ids double as MyAnimeList ids; MAL artwork is larger."""
    images = jikan_anime_images(int(entry["id"]))
    return images.get("maximum_image_url") or images.get("large_image_url") or ""


def graphql_post(query: str) -> dict:
    payload = json.dumps({"query": query}).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}/graphql",
        data=payload,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def character_slug(character: dict) -> str:
    return f"{character['id']}-{slugify(character.get('name') or 'character')}"[:110]


def map_role(roles: list) -> str:
    return "protagonist" if any(role.strip().lower() == "main" for role in roles) else "supporting"


def build_character(role_entry: dict, detail: dict) -> dict:
    character = role_entry.get("character") or {}
    image = (detail.get("image") or {}).get("original") or ""
    if "missing_original" in image:
        image = ""
    japanese = detail.get("japanese") or ""
    return {
        "slug": character_slug(character),
        "name": character.get("russian") or character.get("name") or "",
        "original_name": japanese if isinstance(japanese, str) else "",
        "description": clean_description(detail.get("description") or ""),
        "image_url": f"https://shikimori.io{image}" if image else "",
        "translations": {
            "en": {"name": character.get("name") or character.get("russian") or ""},
            "ru": {"name": character.get("russian") or character.get("name") or ""},
        },
    }


def build_franchises(titles: list, details: dict) -> list:
    groups: dict = {}
    for title in titles:
        franchise_slug = details.get(title["slug"])
        if franchise_slug:
            groups.setdefault(franchise_slug, []).append(title)
    franchises = []
    for franchise_slug, members in groups.items():
        head = min(members, key=lambda title: (title.get("year") or 9999, title["slug"]))
        franchises.append({
            "slug": franchise_slug,
            "name": head["name"],
            "description": "",
            "translations": {
                "en": {"name": head["translations"]["en"]["name"]},
                "ru": {"name": head["name"]},
            },
        })
    return franchises


def clean_description(text: str) -> str:
    return BB_CODE_TAGS.sub("", text).strip()


def map_kind(kind: str) -> str:
    return KIND_MAP.get(kind, "anime")


def map_status(status: str) -> str:
    return STATUS_MAP.get(status, "planned")


def title_slug(entry: dict) -> str:
    return f"{entry['id']}-{slugify(entry.get('name') or 'anime')}"[:100]


def episode_count(entry: dict) -> int:
    if entry.get("status") == "anons":
        return 0
    if entry.get("status") == "ongoing":
        return int(entry.get("episodes_aired") or entry.get("episodes") or 0)
    return int(entry.get("episodes") or 0)


def build_genre(genre: dict) -> dict:
    return {
        "slug": slugify(genre["name"]) or f"genre-{genre['id']}",
        "name": genre["name"],
        "translations": {
            "en": {"name": genre["name"]},
            "ru": {"name": genre.get("russian") or genre["name"]},
        },
    }


def build_title(entry: dict, detail: dict) -> dict:
    romaji = entry.get("name") or ""
    russian = entry.get("russian") or romaji or "Anime"
    english_names = [name for name in (detail.get("english") or []) if name]
    japanese_names = [name for name in (detail.get("japanese") or []) if name]
    aired_on = entry.get("aired_on") or ""
    fallback_poster = (entry.get("image") or {}).get("original") or ""
    if "missing_original" in fallback_poster:
        fallback_poster = ""
    poster = mal_poster(entry) or fallback_poster
    episodes = [
        {"number": number}
        for number in range(1, episode_count(entry) + 1)
    ]
    return {
        "slug": title_slug(entry),
        "name": russian,
        "original_name": (japanese_names or [romaji])[0],
        "synopsis": clean_description(detail.get("description") or ""),
        "title_type": map_kind(entry.get("kind") or "tv"),
        "status": map_status(entry.get("status") or "anons"),
        "year": int(aired_on[:4]) if len(aired_on) >= 4 and aired_on[:4].isdigit() else None,
        "poster_url": poster if poster.startswith("http") else (f"https://shikimori.io{poster}" if poster else ""),
        "genres": [
            slugify(genre["name"]) or f"genre-{genre['id']}"
            for genre in (detail.get("genres") or [])
        ],
        "translations": {
            "en": {"name": (english_names or [romaji or russian])[0]},
            "ru": {"name": russian},
        },
        "episodes": episodes,
    }


class Command(BaseCommand):
    help = (
        "Fetch popular anime metadata from Shikimori and print an import_catalog "
        "JSON payload (dry-run friendly, idempotent on apply)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--page-size", type=int, default=50)
        parser.add_argument("--order", default="popularity")
        parser.add_argument("--characters", type=int, default=8, help="characters per title, 0 disables")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        limit = max(1, options["limit"])
        page_size = min(50, max(1, options["page_size"]))
        entries: list = []
        page = 1
        while len(entries) < limit:
            batch = api_get(
                f"/animes?limit={page_size}&page={page}&order={options['order']}"
            )
            if not batch:
                break
            entries.extend(batch[: limit - len(entries)])
            page += 1
            time.sleep(REQUEST_PAUSE_SECONDS)
        genres: dict = {}
        titles: list = []
        franchise_by_title: dict = {}
        characters: dict = {}
        per_title_limit = max(0, options["characters"])
        for entry in entries:
            time.sleep(REQUEST_PAUSE_SECONDS)
            detail = api_get(f"/animes/{entry['id']}")
            for genre in detail.get("genres") or []:
                built = build_genre(genre)
                genres[built["slug"]] = built
            title = build_title(entry, detail)
            if detail.get("franchise"):
                franchise_by_title[title["slug"]] = str(detail["franchise"])
            if per_title_limit:
                time.sleep(REQUEST_PAUSE_SECONDS)
                roles_response = graphql_post(
                    '{animes(ids:"' + str(entry["id"]) + '"){characterRoles{rolesEn character{id name russian}}}}'
                )
                role_entries = (((roles_response.get("data") or {}).get("animes") or [{}])[0].get("characterRoles")) or []
                links = []
                for sort_order, role_entry in enumerate(role_entries[:per_title_limit]):
                    time.sleep(REQUEST_PAUSE_SECONDS)
                    built = build_character(role_entry, api_get(f"/characters/{role_entry['character']['id']}"))
                    characters[built["slug"]] = built
                    links.append({
                        "character": built["slug"],
                        "role": map_role(role_entry.get("rolesEn") or []),
                        "sort_order": sort_order,
                    })
                title["characters"] = links
            titles.append(title)
            self.stdout.write(f"fetched {entry.get('russian') or entry.get('name')}")
        for title in titles:
            franchise_slug = franchise_by_title.get(title["slug"])
            if franchise_slug:
                title["franchise"] = franchise_slug
        franchises = build_franchises(titles, franchise_by_title)
        payload = {
            "genres": list(genres.values()),
            "franchises": franchises,
            "characters": list(characters.values()),
            "titles": titles,
        }
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as target:
                target.write(serialized + "\n")
            self.stdout.write(
                self.style.SUCCESS(
                    f"wrote {len(titles)} titles, {len(franchises)} franchises, "
                    f"{len(characters)} characters to {options['output']}"
                )
            )
        else:
            self.stdout.write(serialized)
        if not titles:
            raise CommandError("no entries fetched")
