import json
import re
import time
import urllib.request

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

API_BASE = "https://shikimori.one/api"
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
    poster = (entry.get("image") or {}).get("original") or ""
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
        "poster_url": f"https://shikimori.one{poster}" if poster else "",
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
        for entry in entries:
            time.sleep(REQUEST_PAUSE_SECONDS)
            detail = api_get(f"/animes/{entry['id']}")
            for genre in detail.get("genres") or []:
                built = build_genre(genre)
                genres[built["slug"]] = built
            titles.append(build_title(entry, detail))
            self.stdout.write(f"fetched {entry.get('russian') or entry.get('name')}")
        payload = {"genres": list(genres.values()), "titles": titles}
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as target:
                target.write(serialized + "\n")
            self.stdout.write(self.style.SUCCESS(f"wrote {len(titles)} titles to {options['output']}"))
        else:
            self.stdout.write(serialized)
        if not titles:
            raise CommandError("no entries fetched")
