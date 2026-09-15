import difflib
import json
import urllib.error
import urllib.parse
import urllib.request

from . import providers

USER_AGENT = "AniCast/1.0 (creator metadata import)"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class CreatorImageError(RuntimeError):
    pass


def _normalized(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def search_people(name: str) -> list[dict]:
    query = urllib.parse.urlencode({"search": name})
    request = urllib.request.Request(
        f"{providers.api_base()}/people/search?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.URLError) as error:
        raise CreatorImageError("Catalog people request failed") from error
    if len(payload) > MAX_RESPONSE_BYTES:
        raise CreatorImageError("Catalog people response is too large")
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CreatorImageError("Catalog people response is invalid") from error
    if not isinstance(decoded, list) or any(not isinstance(person, dict) for person in decoded):
        raise CreatorImageError("Catalog people response schema is invalid")
    return decoded


def creator_image(name: str) -> str:
    target = _normalized(name)
    people = search_people(name)
    exact = [
        person for person in people
        if target in {_normalized(person.get("name")), _normalized(person.get("russian"))}
    ]
    candidates = exact
    if not candidates:
        scored = []
        for person in people:
            score = max(
                difflib.SequenceMatcher(None, target, _normalized(person.get("name"))).ratio(),
                difflib.SequenceMatcher(None, target, _normalized(person.get("russian"))).ratio(),
            )
            if score >= 0.9:
                scored.append((score, person))
        candidates = [person for _, person in sorted(scored, key=lambda item: item[0], reverse=True)]

    for person in candidates:
        image = person.get("image")
        path = str(image.get("original") or "") if isinstance(image, dict) else ""
        if path.startswith("/system/people/original/") and "missing_" not in path:
            return providers.absolute_url(path)
    return ""
