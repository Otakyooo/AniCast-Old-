import re
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from .management.commands.fetch_shikimori import REQUEST_PAUSE_SECONDS, jikan_get
from .models import Episode, EpisodeTranslation, Title


MAL_ID = re.compile(r"^(\d+)-")
MAX_PAGES = 25
ANIZIP_URL = "https://api.ani.zip/mappings?mal_id={mal_id}"


class EpisodeMetadataError(RuntimeError):
    pass


@dataclass
class EpisodeMetadataResult:
    title: str
    pages: int = 0
    episodes: int = 0
    created: int = 0
    named: int = 0
    dated: int = 0


def _clean_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\xa0", " ").split())[:240]


def _air_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    moment = parse_datetime(value)
    if moment is not None:
        return moment.date()
    return parse_date(value[:10])


def _page(mal_id: int, page: int) -> dict:
    for attempt in range(3):
        try:
            time.sleep(REQUEST_PAUSE_SECONDS + 0.4)
            payload = jikan_get(f"/anime/{mal_id}/episodes?page={page}")
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise EpisodeMetadataError("Jikan episode response schema is invalid")
            return payload
        except Exception as error:
            if attempt == 2:
                raise EpisodeMetadataError("Jikan episode request failed") from error
            time.sleep(3)
    raise EpisodeMetadataError("Jikan episode request failed")


def _anizip_rows(mal_id: int) -> list[dict]:
    """Normalize the ani.zip mapping fallback to Jikan's episode shape.

    ani.zip exposes TVDB-derived dates and multilingual episode titles in one
    bounded response. It is used only when Jikan is unavailable, so the normal
    MAL path and its pagination semantics stay unchanged.
    """
    try:
        result = subprocess.run(
            ["curl", "-sSL", "--fail", "--max-time", "30", "--max-filesize", "20971520", ANIZIP_URL.format(mal_id=mal_id)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise EpisodeMetadataError("Episode metadata providers are unavailable") from error
    episodes = payload.get("episodes") if isinstance(payload, dict) else None
    if not isinstance(episodes, dict):
        raise EpisodeMetadataError("ani.zip episode response schema is invalid")
    rows = []
    for raw_number, item in episodes.items():
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("absoluteEpisodeNumber") or raw_number)
        except (TypeError, ValueError):
            continue
        titles = item.get("title") if isinstance(item.get("title"), dict) else {}
        rows.append({
            "mal_id": number,
            "title": titles.get("en") or titles.get("x-jat") or "",
            "title_japanese": titles.get("ja") or "",
            "title_russian": titles.get("ru") or "",
            "aired": item.get("airDateUtc") or item.get("airDate"),
        })
    return rows


def _fill_translation(episode: Episode, language: str, name: str) -> bool:
    if not name:
        return False
    translation, created = EpisodeTranslation.objects.get_or_create(
        episode=episode,
        language=language,
        defaults={"name": name},
    )
    if not created and not translation.name:
        translation.name = name
        translation.save(update_fields=["name"])
        return True
    return created


def sync_title_episode_metadata(title: Title, *, max_pages: int = MAX_PAGES) -> EpisodeMetadataResult:
    match = MAL_ID.match(title.slug)
    if match is None:
        raise ValueError("Title slug does not contain a MyAnimeList id")
    if not 1 <= max_pages <= MAX_PAGES:
        raise ValueError(f"max_pages must be between 1 and {MAX_PAGES}")

    mal_id = int(match.group(1))
    rows: list[dict] = []
    page_number = 1
    try:
        while page_number <= max_pages:
            payload = _page(mal_id, page_number)
            rows.extend(row for row in payload["data"] if isinstance(row, dict))
            pagination = payload.get("pagination") or {}
            if not pagination.get("has_next_page"):
                break
            page_number += 1
        else:
            if (payload.get("pagination") or {}).get("has_next_page"):
                raise EpisodeMetadataError("Jikan episode pagination exceeds the safety limit")
    except EpisodeMetadataError:
        rows = _anizip_rows(mal_id)
        page_number = 1

    result = EpisodeMetadataResult(title=title.slug, pages=page_number)
    with transaction.atomic():
        episodes = {episode.number: episode for episode in Episode.objects.filter(title=title)}
        for row in rows:
            number = row.get("mal_id")
            if type(number) is not int or number < 1:
                continue
            episode = episodes.get(number)
            if episode is None:
                episode = Episode.objects.create(title=title, number=number)
                episodes[number] = episode
                result.created += 1

            english = _clean_name(row.get("title")) or _clean_name(row.get("title_romanji"))
            japanese = _clean_name(row.get("title_japanese"))
            russian = _clean_name(row.get("title_russian"))
            update_fields: list[str] = []
            if not episode.name and english:
                episode.name = english
                update_fields.append("name")
                result.named += 1
            aired_on = _air_date(row.get("aired"))
            # Exact Kodik timestamps have higher precision and therefore win.
            if episode.air_at is None and episode.air_date is None and aired_on is not None:
                episode.air_date = aired_on
                update_fields.append("air_date")
                result.dated += 1
            if update_fields:
                episode.save(update_fields=update_fields)
            _fill_translation(episode, "en", english)
            _fill_translation(episode, "ja", japanese)
            _fill_translation(episode, "ru", russian)
            result.episodes += 1
    return result
