import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings


API_BASE = "https://kodik-api.com"
PLAYER_HOST = "kodikplayer.com"
PLAYER_PATHS = {"season", "seria", "serial", "video"}
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 20
SOURCE_URL_MAX_LENGTH = 200


class KodikAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class KodikSearchResult:
    total: int
    results: list[dict[str, Any]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post_json(path: str, params: dict[str, object]) -> dict[str, Any]:
    token = settings.KODIK_API_TOKEN
    if not token:
        raise KodikAPIError("KODIK_API_TOKEN is not configured")
    body = urllib.parse.urlencode({"token": token, **params}).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "AniCast/1.0"},
        method="POST",
    )
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get_content_type()
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
        raise KodikAPIError("Kodik API request failed") from error
    if content_type != "application/json" or len(payload) > MAX_RESPONSE_BYTES:
        raise KodikAPIError("Kodik API returned an invalid response")
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise KodikAPIError("Kodik API returned invalid JSON") from error
    if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
        raise KodikAPIError("Kodik API response schema is invalid")
    return decoded


def search_by_shikimori(
    shikimori_id: int,
    *,
    limit: int = 100,
    season: int | None = None,
    with_material_data: bool = False,
) -> KodikSearchResult:
    if type(shikimori_id) is not int or shikimori_id < 1:
        raise ValueError("shikimori_id must be a positive integer")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    params: dict[str, object] = {
        "shikimori_id": shikimori_id,
        "limit": limit,
        "with_episodes_data": "true",
        "not_blocked_for_me": "true",
    }
    if season is not None:
        params["season"] = season
    if with_material_data:
        params["with_material_data"] = "true"
    payload = _post_json("/search", params)
    total = payload.get("total")
    results = payload["results"]
    if type(total) is not int or total < 0 or any(not isinstance(result, dict) for result in results):
        raise KodikAPIError("Kodik API response schema is invalid")
    return KodikSearchResult(total=total, results=results)


def player_url_allowed(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    path_parts = parsed.path.strip("/").split("/")
    return (
        parsed.scheme == "https"
        and parsed.hostname == PLAYER_HOST
        and len(path_parts) >= 3
        and path_parts[0] in PLAYER_PATHS
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
        and not parsed.fragment
    )


def normalize_player_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = f"https:{value}" if value.startswith("//") else value
    if len(normalized) > SOURCE_URL_MAX_LENGTH:
        return None
    return normalized if player_url_allowed(normalized) else None
