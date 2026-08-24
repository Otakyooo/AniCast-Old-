"""Poster mirroring and automatic quality upgrade.

Every title gets a locally served copy of its best available artwork so
page renders never depend on third-party CDNs. Quality follows MyAnimeList
artwork through Jikan with three tiers encoded in the stored filename:

- ``m``: MAL ``maximum_image_url``
- ``l``: MAL ``large_image_url`` fallback
- ``s``: current Shikimori/MAL hotlink mirrored as-is

Titles below the ``m`` tier are re-probed by the scheduled Celery task,
so posters converge to the best artwork once upstream recovers without
manual reruns.
"""

import hashlib
import os
import re
import struct
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin

from django.conf import settings

from catalog.management.commands import fetch_shikimori
from catalog.models import Title
from common.metrics import increment

TIER_MAXIMUM = "m"
TIER_LARGE = "l"
TIER_FALLBACK = "s"

ALLOWED_POSTER_HOSTS = frozenset({"shikimori.one", "shikimori.io", "cdn.myanimelist.net"})
POSTER_NAME_RE = re.compile(r"^(\d{1,7}|x)-([mls])-([0-9a-f]{8}|[0-9a-f]{16})\.(jpg|png|webp)$")
MEDIA_PATH_MARKER = "/api/v1/media/posters/"
MIN_WIDTH = 200
MIN_HEIGHT = 280
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_REDIRECT_HOPS = 3
DIGEST_HEX_CHARS = 16
BATCH_TIME_BUDGET_SECONDS = 1300
PART_FILE_MAX_AGE_SECONDS = 3600
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_CURL_TRAILER = "\n===anicast:%{http_code}|%{redirect_url}"

_SOF_MARKERS = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})


def ensure_media_dir() -> Path:
    root = Path(settings.POSTERS_MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


def media_root() -> Path:
    return Path(settings.POSTERS_MEDIA_ROOT)


def media_path(filename: str) -> Path:
    return media_root() / filename


def public_poster_url(filename: str) -> str:
    return f"{settings.POSTERS_PUBLIC_BASE}{MEDIA_PATH_MARKER}{filename}"


def is_allowed_poster_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_POSTER_HOSTS


def current_tier(poster_url: str) -> str | None:
    marker = poster_url.rfind(MEDIA_PATH_MARKER)
    if marker < 0:
        return None
    match = POSTER_NAME_RE.match(poster_url[marker + len(MEDIA_PATH_MARKER):])
    return match.group(2) if match else None


def stored_tier(poster_url: str) -> str | None:
    """Tier of a local poster that still exists on disk; None otherwise.

    A missing file downgrades the title to an adoption candidate so the
    pipeline re-downloads artwork after volume loss instead of skipping it.
    """
    tier = current_tier(poster_url)
    if tier is None:
        return None
    filename = poster_url.rsplit("/", 1)[-1]
    return tier if media_path(filename).is_file() else None


def slug_mal_id(slug: str) -> int | None:
    prefix = slug.split("-", 1)[0]
    return int(prefix) if prefix.isdigit() else None


def image_dimensions(data: bytes) -> tuple[str, int, int]:
    """Return ``(ext, width, height)`` for supported JPEG/PNG payloads."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in _SOF_MARKERS:
                height, width = struct.unpack(">HH", data[index + 5:index + 9])
                return "jpg", width, height
            if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            index += 2 + struct.unpack(">H", data[index + 2:index + 4])[0]
    raise ValueError("unsupported image payload")


def _fetch_hop(url: str) -> tuple[int, bytes, str]:
    """One allowlisted HTTPS hop with a hard in-memory cap.

    Streams at most ``MAX_IMAGE_BYTES + 1`` bytes regardless of whether
    the upstream sends Content-Length, so chunked responses cannot balloon
    worker memory. The write-out trailer carries status and redirect URL.
    """
    proc = subprocess.Popen(
        ["curl", "-sS", "--fail", "--max-time", "20",
         "--max-filesize", str(MAX_IMAGE_BYTES), "-w", _CURL_TRAILER, url],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert proc.stdout is not None
    payload = proc.stdout.read(MAX_IMAGE_BYTES + 1)
    proc.stdout.close()
    returncode = proc.wait()
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("poster exceeds size cap")
    if returncode != 0:
        raise OSError(f"curl exit {returncode}")
    trailer_at = payload.rfind(b"\n===anicast:")
    body = payload[:trailer_at] if trailer_at >= 0 else payload
    match = re.search(rb"===anicast:(\d{3})\|([^\n]*)\n?$", payload[trailer_at:] if trailer_at >= 0 else b"")
    status = int(match.group(1)) if match else (200 if returncode == 0 else 0)
    redirect_url = (match.group(2).decode("ascii", "replace").strip() if match else "") or ""
    return status, body, redirect_url


def download_bytes(url: str) -> bytes:
    # Jikan's edge rejects the python TLS fingerprint while curl works,
    # matching the lookup approach in fetch_shikimori. Redirects are
    # followed one hop at a time and every target must stay on an
    # allowlisted HTTPS host.
    current = url
    for _ in range(MAX_REDIRECT_HOPS + 1):
        if not is_allowed_poster_url(current):
            raise ValueError("poster host not allowed")
        status, body, redirect_url = _fetch_hop(current)
        if status in REDIRECT_STATUSES:
            if not redirect_url:
                raise ValueError("redirect without location")
            current = urljoin(current, redirect_url)
            continue
        if status < 200 or status >= 300:
            raise OSError(f"unexpected status {status}")
        return body
    raise ValueError("too many redirects")


def poster_extension(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpg"
    raise ValueError("unsupported image payload")


def store_poster(mal_id: int | None, tier: str, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:DIGEST_HEX_CHARS]
    filename = f"{mal_id if mal_id is not None else 'x'}-{tier}-{digest}.{poster_extension(data)}"
    target = ensure_media_dir() / filename
    if target.exists():
        existing = target.read_bytes()
        if hashlib.sha256(existing).hexdigest()[:DIGEST_HEX_CHARS] != digest:
            raise ValueError("poster digest collision with different content")
        return filename
    tmp = target.with_name(f"{target.name}.{os.getpid()}.part")
    tmp.write_bytes(data)
    tmp.replace(target)
    return filename


def drop_stored_poster(poster_url: str) -> None:
    marker = poster_url.rfind(MEDIA_PATH_MARKER)
    if marker < 0:
        return
    filename = poster_url[marker + len(MEDIA_PATH_MARKER):]
    if POSTER_NAME_RE.match(filename):
        media_path(filename).unlink(missing_ok=True)


def mal_artwork_with_tier(mal_id: int) -> tuple[str, str] | None:
    """Best MAL artwork URL with its tier, or None when Jikan has none."""
    images = fetch_shikimori.jikan_anime_images(mal_id)
    maximum = images.get("maximum_image_url") or ""
    large = images.get("large_image_url") or ""
    if maximum.startswith("https://cdn.myanimelist.net/"):
        return maximum, TIER_MAXIMUM
    if large.startswith("https://cdn.myanimelist.net/"):
        return large, TIER_LARGE
    return None


def _ensure_origin(title: Title, apply_changes: bool) -> None:
    """Backfill a reconstructable remote source for legacy mirrored rows."""
    if title.poster_origin_url or current_tier(title.poster_url) is None:
        return
    mal_id = slug_mal_id(title.slug)
    if mal_id is None:
        return
    origin = f"https://shikimori.one/system/animes/original/{mal_id}.jpg"
    if apply_changes:
        Title.objects.filter(pk=title.pk).update(poster_origin_url=origin)
    title.poster_origin_url = origin


def refresh_title(title: Title, apply_changes: bool) -> tuple[str, str]:
    """Bring one title to its best stable poster. Returns ``(result, detail)``."""
    if apply_changes:
        _ensure_origin(title, True)
    mal_id = slug_mal_id(title.slug)
    tier = stored_tier(title.poster_url)
    best = mal_artwork_with_tier(mal_id) if mal_id is not None else None
    if best is not None:
        url, best_tier = best
        improves = best_tier == TIER_MAXIMUM and tier != TIER_MAXIMUM
        improves |= best_tier == TIER_LARGE and tier in (None, TIER_FALLBACK)
        if improves and is_allowed_poster_url(url):
            return _adopt_labeled(title, mal_id, url, best_tier, apply_changes)
        increment("poster_refresh", "current")
        return "current", f"{title.slug}: already at tier {tier or 'none'}"
    mirror_source = next(
        (candidate for candidate in (title.poster_url, title.poster_origin_url)
         if candidate and is_allowed_poster_url(candidate)),
        "",
    )
    if tier is None and mirror_source:
        return _adopt_labeled(title, mal_id, mirror_source, TIER_FALLBACK, apply_changes)
    increment("poster_refresh", "unavailable")
    return "unavailable", f"{title.slug}: no artwork upgrade available"


def _adopt_labeled(
    title: Title,
    mal_id: int | None,
    url: str,
    tier: str,
    apply_changes: bool,
) -> tuple[str, str]:
    try:
        return _adopt(title, mal_id, url, tier, apply_changes)
    except ValueError as reason:
        # Rejected content: bad payload, undersized image, digest collision.
        increment("poster_refresh", "invalid")
        return "invalid", f"{title.slug}: artwork rejected ({reason})"
    except Exception:
        increment("poster_refresh", "error")
        return "error", f"{title.slug}: download failed"


def _adopt(title: Title, mal_id: int | None, url: str, tier: str, apply_changes: bool) -> tuple[str, str]:
    verb = {"m": "maximum", "l": "large", "s": "mirrored"}[tier]
    if not apply_changes:
        return verb, f"{title.slug}: plan {tier}-tier from {url.split('//', 1)[-1].split('/', 1)[0]}"
    data = download_bytes(url)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("poster too large")
    ext, width, height = image_dimensions(data)
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise ValueError(f"poster {width}x{height} below minimum")
    filename = store_poster(mal_id, tier, data)
    public_url = public_poster_url(filename)
    previous = title.poster_url
    origin = title.poster_origin_url
    if current_tier(previous) is None and previous and is_allowed_poster_url(previous):
        origin = previous
    updates: dict[str, str] = {"poster_url": public_url}
    if origin and current_tier(origin) is None:
        updates["poster_origin_url"] = origin
    Title.objects.filter(pk=title.pk).update(**updates)
    if current_tier(previous) is not None and previous != public_url:
        drop_stored_poster(previous)
    increment("poster_refresh", verb)
    return verb, f"{title.slug}: stored {filename} ({width}x{height}, {ext})"


def sweep_part_files() -> int:
    """Delete stale partial downloads left behind by hard kills."""
    cutoff = time.time() - PART_FILE_MAX_AGE_SECONDS
    removed = 0
    for part in media_root().glob("*.part"):
        try:
            if part.stat().st_mtime < cutoff:
                part.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def refresh_batch(
    limit: int = 0,
    apply_changes: bool = False,
    deadline: float | None = None,
) -> list[tuple[str, str]]:
    """Upgrade up to ``limit`` titles that are not yet at maximum tier.

    Candidates are sampled randomly so scheduled runs spread retry
    attempts fairly instead of replaying the same low-id slice.
    ``deadline`` (a ``time.monotonic()`` value) stops new work in time to
    respect the Celery soft time limit.
    """
    outcomes: list[tuple[str, str]] = []
    sweep_part_files()
    for title in Title.objects.order_by("?").only("id", "slug", "poster_url", "poster_origin_url").iterator():
        if stored_tier(title.poster_url) == TIER_MAXIMUM:
            continue
        if deadline is not None and time.monotonic() >= deadline:
            break
        try:
            outcomes.append(refresh_title(title, apply_changes))
        except Exception:
            increment("poster_refresh", "error")
            outcomes.append(("error", f"{title.slug}: refresh failed"))
        if 0 < limit <= len(outcomes):
            break
    return outcomes


def restore_origins(apply_changes: bool = False) -> list[tuple[str, str]]:
    """Point ``poster_url`` back at recorded remote sources.

    Recovery path after a rollback to an image without the poster media
    route: run this forward first, then roll the image back safely.
    """
    outcomes: list[tuple[str, str]] = []
    queryset = Title.objects.exclude(poster_origin_url="").exclude(poster_url="").order_by("id")
    for title in queryset.only("id", "slug", "poster_url", "poster_origin_url").iterator():
        if current_tier(title.poster_url) is None:
            continue
        origin = title.poster_origin_url
        if not is_allowed_poster_url(origin):
            continue
        result = "restored"
        if apply_changes:
            Title.objects.filter(pk=title.pk).update(poster_url=origin)
        else:
            result = "plan"
        outcomes.append((result, f"{title.slug}: {urlparse(origin).hostname}"))
    return outcomes
