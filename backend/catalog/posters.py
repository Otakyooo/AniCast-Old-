"""Poster mirroring and automatic quality upgrade.

Every title gets a locally served copy of its best available artwork so
page renders never depend on third-party CDNs. Quality follows MyAnimeList
artwork through Jikan with tiers encoded in the stored filename:

- ``m``: MAL ``maximum_image_url``
- ``l``: MAL ``large_image_url`` fallback
- ``k``: Kitsu ``posterImage.original`` (fallback while Jikan is degraded)
- ``o``: recorded catalog origin (``poster_origin_url``), adopted when
  strictly larger than the stored file
- ``s``: current catalog fallback mirrored as-is

Non-maximum artwork is only replaced when the downloaded file is strictly
larger than what is already stored, so upgrades never lose pixels. Titles
below the ``m`` tier are re-probed by the scheduled Celery task, so posters
converge to the best artwork once upstreams recover without manual reruns.
"""

import hashlib
import ipaddress
import json
import os
import random
import re
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin

from django.conf import settings

from catalog.management.commands import fetch_shikimori
from catalog.models import Title
from common.metrics import increment

from . import providers

TIER_MAXIMUM = "m"
TIER_LARGE = "l"
TIER_KITSU = "k"
TIER_ORIGIN = "o"
TIER_FALLBACK = "s"

# The provider's own hosts come from configuration so a domain move is an env
# change; the other entries are independent artwork CDNs, not aliases of it.
ALLOWED_POSTER_HOSTS = providers.asset_hosts() | frozenset(
    {"cdn.myanimelist.net", "media.kitsu.app", "media.kitsu.io"}
)
POSTER_NAME_RE = re.compile(r"^(\d{1,7}|x)-([mlsko])-([0-9a-f]{8}|[0-9a-f]{16})\.(jpg|png|webp)$")
MEDIA_PATH_MARKER = "/api/v1/media/posters/"
MIN_WIDTH = 200
MIN_HEIGHT = 280
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_REDIRECT_HOPS = 3
DIGEST_HEX_CHARS = 16
BATCH_TIME_BUDGET_SECONDS = 1300
BATCH_HARD_CAP = 120
PART_FILE_MAX_AGE_SECONDS = 3600
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_CURL_TRAILER = "\n===anicast:%{http_code}|%{redirect_url}"

MAL_TO_KITSU_MAPPING_URL = "https://api.ani.zip/mappings?mal_id={mal_id}"
KITSU_ANIME_URL = "https://kitsu.io/api/edge/anime/{kitsu_id}?fields%5Banime%5D=posterImage"
_LOOKUP_HOSTS = frozenset({"api.ani.zip", "kitsu.io"})

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


def public_poster_reference(poster_url: str) -> str:
    """Expose only an AniCast media URL, never a recorded upstream URL."""
    marker = poster_url.rfind(MEDIA_PATH_MARKER)
    if marker < 0:
        return ""
    path = poster_url[marker:]
    filename = path.removeprefix(MEDIA_PATH_MARKER)
    return public_poster_url(filename) if POSTER_NAME_RE.fullmatch(filename) else ""


def is_allowed_poster_url(url: str) -> bool:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_POSTER_HOSTS
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and not parsed.fragment
    )


def assert_poster_destination_global(url: str) -> None:
    """Reject allowlisted hosts resolving to private/reserved addresses.

    An allowlisted CDN hostname (or its redirect target) compromised via DNS
    or CNAME could otherwise turn the artwork fetcher into an intranet probe.
    Fail-closed: DNS errors reject the hop.
    """
    hostname = urlparse(url).hostname
    if not hostname:
        raise ValueError("poster URL has no hostname")
    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise ValueError(f"poster DNS failed: {error}") from error
    addresses = {item[4][0] for item in infos}
    if not addresses:
        raise ValueError("poster DNS returned no address")
    for address in addresses:
        try:
            if not ipaddress.ip_address(address).is_global:
                raise ValueError("poster DNS points to private or reserved address")
        except ValueError as error:
            if "private or reserved" in str(error):
                raise
            raise ValueError(f"poster address unparsable: {address}") from error


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
    # The artwork edge rejects the python TLS fingerprint while curl works.
    # Redirects are
    # followed one hop at a time and every target must stay on an
    # allowlisted HTTPS host.
    current = url
    for _ in range(MAX_REDIRECT_HOPS + 1):
        if not is_allowed_poster_url(current):
            raise ValueError("poster host not allowed")
        assert_poster_destination_global(current)
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
    tmp = target.with_name(f"{target.name}.{os.getpid()}.{threading.get_ident()}.part")
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


def _fetch_json(url: str) -> dict | None:
    """Bounded GET of a small JSON lookup response from an allowlisted host."""
    current = url
    for _ in range(MAX_REDIRECT_HOPS + 1):
        parsed = urlparse(current)
        if parsed.scheme != "https" or parsed.hostname not in _LOOKUP_HOSTS:
            return None
        try:
            status, body, redirect_url = _fetch_hop(current)
        except (OSError, ValueError):
            return None
        if status in REDIRECT_STATUSES:
            if not redirect_url:
                return None
            current = urljoin(current, redirect_url)
            continue
        if status != 200 or not body:
            return None
        try:
            payload = json.loads(body)
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None
    return None


def kitsu_original_for_mal(mal_id: int) -> str | None:
    """Kitsu ``posterImage.original`` URL for a MAL id, or None.

    Resolution goes through the ani.zip offline mapping (``mappings.kitsu_id``)
    followed by one Kitsu API call. Every failure mode degrades to None so the
    caller simply falls back to the next-best source.
    """
    mapping = _fetch_json(MAL_TO_KITSU_MAPPING_URL.format(mal_id=mal_id))
    kitsu_id = mapping.get("mappings", {}).get("kitsu_id") if mapping else None
    if not isinstance(kitsu_id, int) or kitsu_id <= 0:
        return None
    payload = _fetch_json(KITSU_ANIME_URL.format(kitsu_id=kitsu_id))
    original = payload.get("data", {}).get("attributes", {}).get("posterImage", {}).get("original", "") if payload else ""
    if isinstance(original, str) and urlparse(original).hostname in {"media.kitsu.app", "media.kitsu.io"}:
        return original
    return None


def _ensure_origin(title: Title, apply_changes: bool) -> None:
    """Backfill a reconstructable remote source for legacy mirrored rows."""
    if title.poster_origin_url or current_tier(title.poster_url) is None:
        return
    mal_id = slug_mal_id(title.slug)
    if mal_id is None:
        return
    origin = providers.absolute_url(f"/system/animes/original/{mal_id}.jpg")
    if apply_changes:
        Title.objects.filter(pk=title.pk).update(poster_origin_url=origin)
    title.poster_origin_url = origin


def refresh_title(title: Title, apply_changes: bool) -> tuple[str, str]:
    """Bring one title to its best stable poster. Returns ``(result, detail)``."""
    # Capture the persisted origin before _ensure_origin reconstructs one:
    # only origins recorded before this refresh are upgrade candidates, so a
    # legacy row finishes its regular upgrade first and becomes an origin
    # candidate from the next cycle on.
    recorded_origin = title.poster_origin_url
    if apply_changes:
        _ensure_origin(title, True)
    mal_id = slug_mal_id(title.slug)
    tier = stored_tier(title.poster_url)
    if tier == TIER_MAXIMUM:
        # Nothing can beat the maximum artwork; never spend probes on it.
        increment("poster_refresh", "current")
        return "current", f"{title.slug}: already at tier {tier}"
    best = mal_artwork_with_tier(mal_id) if mal_id is not None else None
    if best is not None:
        url, best_tier = best
        if best_tier == TIER_MAXIMUM and tier != TIER_MAXIMUM:
            return _adopt_labeled(title, mal_id, url, best_tier, apply_changes)
    # Origin upgrades only apply to titles already serving a local copy;
    # raw-hotlink rows take the cheaper mirror path below first (same bytes,
    # and the very next refresh sees them as upgraded candidates).
    if (
        recorded_origin
        and is_allowed_poster_url(recorded_origin)
        and current_tier(title.poster_url) is not None
    ):
        upgraded, detail = _adopt_if_larger(title, mal_id, recorded_origin, TIER_ORIGIN, apply_changes)
        if upgraded == "original":
            return upgraded, detail
        # current/invalid/error fall through: a failed origin download must
        # never block the remaining large/kitsu sources.
    # Kitsu originals are frequently far larger than MAL large art, so this
    # probe runs before the large fallback; a Kitsu adoption ends the refresh,
    # anything else (kept/rejected/failed) falls through to MAL large.
    kitsu_outcome = None
    kitsu_url = kitsu_original_for_mal(mal_id) if mal_id is not None else None
    if kitsu_url:
        kitsu_outcome = _adopt_if_larger(title, mal_id, kitsu_url, TIER_KITSU, apply_changes)
        if kitsu_outcome[0] == "kitsu":
            return kitsu_outcome
    if best is not None:
        url, best_tier = best
        if best_tier == TIER_LARGE:
            if tier in (None, TIER_FALLBACK):
                return _adopt_labeled(title, mal_id, url, best_tier, apply_changes)
            if tier in (TIER_KITSU, TIER_LARGE):
                # Both sides are per-title sized fallbacks; keep the larger.
                return _adopt_if_larger(title, mal_id, url, TIER_LARGE, apply_changes)
            increment("poster_refresh", "current")
            return "current", f"{title.slug}: already at tier {tier}"
    if kitsu_outcome is not None:
        return kitsu_outcome
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


def _stored_dimensions(poster_url: str) -> tuple[int, int] | None:
    """Pixel size of the local poster file; None when unreadable or absent."""
    filename = poster_url.rsplit("/", 1)[-1]
    target = media_path(filename)
    if current_tier(poster_url) is None or not target.is_file():
        return None
    try:
        _, width, height = image_dimensions(target.read_bytes())
    except (OSError, ValueError):
        return None
    return width, height


def _adopt_if_larger(
    title: Title,
    mal_id: int | None,
    url: str,
    tier: str,
    apply_changes: bool,
) -> tuple[str, str]:
    """Adopt fallback-tier artwork only when it strictly beats the stored file.

    Kitsu originals and MAL large art have per-title sizes that no tier label
    can predict, so the decision compares real pixel dimensions. Equal or
    smaller candidates never replace existing art (no churn, no quality loss).
    """
    if not apply_changes:
        host = url.split("//", 1)[-1].split("/", 1)[0]
        return "plan", f"{title.slug}: plan {tier}-tier from {host}"
    try:
        data = download_bytes(url)
        ext, width, height = image_dimensions(data)
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            raise ValueError(f"poster {width}x{height} below minimum")
        stored = _stored_dimensions(title.poster_url)
        if stored is not None and width * height <= stored[0] * stored[1]:
            increment("poster_refresh", "current")
            return "current", f"{title.slug}: kept {stored[0]}x{stored[1]} over {width}x{height}"
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
        verb = {"k": "kitsu", "l": "large", "o": "original"}[tier]
        increment("poster_refresh", verb)
        return verb, f"{title.slug}: stored {filename} ({width}x{height}, {ext})"
    except ValueError as reason:
        increment("poster_refresh", "invalid")
        return "invalid", f"{title.slug}: artwork rejected ({reason})"
    except Exception:
        increment("poster_refresh", "error")
        return "error", f"{title.slug}: download failed"


def _adopt(title: Title, mal_id: int | None, url: str, tier: str, apply_changes: bool) -> tuple[str, str]:
    verb = {"m": "maximum", "l": "large", "k": "kitsu", "o": "original", "s": "mirrored"}[tier]
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


def _candidate_priority(title: Title) -> int | None:
    """Work bucket for a non-maximum title; None removes it from the queue.

    0 — nothing usable on disk (missing local file or no poster yet):
        restore or first-mirror work that directly affects viewers;
    1 — fallback tier: provider-resolution art awaiting an upgrade;
    2 — large/kitsu/origin tiers: already upgraded, only probing for maximum.
    Titles with neither an allowlisted source nor a MAL id in the slug can
    never improve and are dropped instead of burning probes every run.
    """
    tier = stored_tier(title.poster_url)
    if tier == TIER_MAXIMUM:
        return None
    if tier == TIER_FALLBACK:
        return 1
    if tier in (TIER_LARGE, TIER_KITSU, TIER_ORIGIN):
        return 2
    if any(url and is_allowed_poster_url(url) for url in (title.poster_url, title.poster_origin_url)):
        return 0
    if stored_tier(title.poster_url) is None and slug_mal_id(title.slug) is not None:
        return 0
    return None


def refresh_batch(
    limit: int = 0,
    apply_changes: bool = False,
    deadline: float | None = None,
) -> list[tuple[str, str]]:
    """Upgrade titles that are not yet at maximum quality.

    Work is prioritised: broken/missing posters first, then fallback-tier
    art, then large-tier re-probes; within a bucket candidates are sampled
    randomly so scheduled runs spread attempts fairly. ``limit`` caps the
    outcome count (0 = budget-driven); ``deadline`` (a ``time.monotonic()``
    value) stops new work in time to respect the Celery soft time limit.
    """
    outcomes: list[tuple[str, str]] = []
    sweep_part_files()
    rows = list(Title.objects.order_by("id").only("id", "slug", "poster_url", "poster_origin_url"))
    buckets: dict[int, list[Title]] = {0: [], 1: [], 2: []}
    for title in rows:
        priority = _candidate_priority(title)
        if priority is not None:
            buckets[priority].append(title)
    ordered = [title for bucket in buckets.values() for title in random.sample(bucket, k=len(bucket))]
    for title in ordered:
        if deadline is not None and time.monotonic() >= deadline:
            break
        try:
            outcomes.append(refresh_title(title, apply_changes))
        except Exception:
            increment("poster_refresh", "error")
            outcomes.append(("error", f"{title.slug}: refresh failed"))
        if len(outcomes) >= BATCH_HARD_CAP:
            break
        if 0 < limit <= len(outcomes):
            break
    return outcomes
