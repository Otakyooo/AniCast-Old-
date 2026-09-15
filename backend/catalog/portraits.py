"""Private-origin portrait cache for public character and creator images.

Catalog imports may keep a provider URL internally so artwork can be refreshed,
but browsers only receive pre-mirrored AniCast media. Public requests never
perform outbound network work.
"""

from pathlib import Path
from urllib.parse import urlparse

from . import posters, providers


PORTRAIT_KINDS = frozenset({"characters", "creators"})
ALLOWED_ORIGIN_HOSTS = providers.asset_hosts() | frozenset({"cdn.myanimelist.net"})
MIN_WIDTH = 40
MIN_HEIGHT = 40


def is_allowed_origin(source_url: str) -> bool:
    parsed = urlparse(source_url)
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_ORIGIN_HOSTS
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and not parsed.fragment
    )


def public_portrait_url(
    kind: str,
    object_id: int,
    image_url: str,
    origin_url: str = "",
) -> str:
    """Return verified local artwork, never a private origin or lazy fetch."""
    if kind not in PORTRAIT_KINDS:
        return ""
    local = posters.public_poster_reference(image_url)
    if local and posters.stored_tier(image_url):
        return local
    return ""


def _store(data: bytes) -> Path:
    extension, width, height = posters.image_dimensions(data)
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise ValueError(f"portrait {width}x{height} below minimum")
    filename = posters.store_poster(None, posters.TIER_FALLBACK, data)
    target = posters.media_path(filename)
    if target.suffix != f".{extension}":
        raise ValueError("portrait extension mismatch")
    return target


def mirror_portrait(source_url: str) -> Path:
    """Download and verify a private portrait for an operator/background job."""
    if not is_allowed_origin(source_url):
        raise ValueError("portrait origin not allowed")
    return _store(posters.download_bytes(source_url))


def portrait_record(kind: str, object_id: int):
    """Read one portrait-bearing record without exposing its private origin."""
    from .models import Character, Creator

    model = Character if kind == "characters" else Creator if kind == "creators" else None
    if model is None:
        return None
    return model.objects.filter(pk=object_id).only("id", "image_url", "image_origin_url").first()


def mirror_record(kind: str, record) -> Path:
    """Mirror one model object and atomically switch its public field local."""
    if kind not in PORTRAIT_KINDS:
        raise ValueError("portrait kind not allowed")
    if posters.stored_tier(record.image_url):
        return posters.media_path(record.image_url.rsplit("/", 1)[-1])
    source_url = str(record.image_origin_url or record.image_url or "")
    path = mirror_portrait(source_url)
    public_url = posters.public_poster_url(path.name)
    if record.image_url != public_url:
        type(record).objects.filter(pk=record.pk).update(image_url=public_url)
        record.image_url = public_url
    return path


def set_private_origin(record, source_url: str) -> bool:
    """Update a provider origin and invalidate only our generated fallback."""
    if not is_allowed_origin(source_url) or record.image_origin_url == source_url:
        return False
    updates = {"image_origin_url": source_url}
    if posters.current_tier(record.image_url) == posters.TIER_FALLBACK:
        updates["image_url"] = ""
        record.image_url = ""
    type(record).objects.filter(pk=record.pk).update(**updates)
    record.image_origin_url = source_url
    return True
