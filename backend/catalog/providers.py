"""Give the metadata provider one configurable address.

Shikimori is a Russian community site that has already moved domains
(``shikimori.org`` -> ``shikimori.one`` -> ``shikimori.io``; the retired hosts
now answer 301/308 to the live one) and may move again. Its address is therefore
configuration, not a constant: point ``ANICAST_METADATA_BASE_URL`` somewhere else
and the whole import pipeline follows without a code change.

Stored artwork is matched against every known alias rather than the current base
alone, so rows written before a move stay valid instead of being rejected as an
untrusted origin — and a dead alias is never a reason to trust an arbitrary host.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from django.conf import settings


def base_url() -> str:
    """The live provider address, without a trailing slash."""
    return str(settings.METADATA_BASE_URL).rstrip("/")


def api_base() -> str:
    return f"{base_url()}/api"


def graphql_url() -> str:
    return f"{api_base()}/graphql"


def asset_hosts() -> frozenset[str]:
    """Hosts accepted as this provider's artwork: the live one plus aliases."""
    hosts = {urlparse(base_url()).hostname or ""}
    hosts.update(str(host).strip().lower() for host in settings.METADATA_ASSET_HOSTS)
    hosts.discard("")
    return frozenset(hosts)


def absolute_url(path_or_url: str) -> str:
    """Absolute provider URL for a relative path; an absolute URL passes through."""
    value = str(path_or_url or "")
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(f"{base_url()}/", value.lstrip("/"))


def is_asset_url(url: str) -> bool:
    """Whether a URL is artwork we may fetch from the provider."""
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in asset_hosts()
