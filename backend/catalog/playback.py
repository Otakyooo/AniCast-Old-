import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from .models import RightsGrant, Source

PLAYBACK_TOKEN_SALT = "catalog.playback.v1"
MAX_PLAYBACK_TTL_SECONDS = 300
HOST_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
SENSITIVE_CONFIG_KEYS = {"api_key", "authorization", "credential", "password", "secret", "token"}


@dataclass(frozen=True)
class PlaybackTarget:
    mode: str
    url: str
    expires_at: datetime


class PlaybackAdapter(Protocol):
    name: str

    def validate_config(self, config: object) -> None: ...

    def target_url(self, source: Source) -> str: ...


class ExternalLinkAdapter:
    name = "external_link"

    def validate_config(self, config: object) -> None:
        if config != {}:
            raise ValueError("external_link adapter does not accept configuration")

    def target_url(self, source: Source) -> str:
        return source.url


class PlaybackAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, PlaybackAdapter] = {}

    def register(self, adapter: PlaybackAdapter) -> None:
        if not adapter.name or adapter.name in self._adapters:
            raise ValueError("Playback adapter names must be non-empty and unique")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> PlaybackAdapter | None:
        return self._adapters.get(name)


playback_adapters = PlaybackAdapterRegistry()
playback_adapters.register(ExternalLinkAdapter())


def playback_url_ttl() -> int:
    return max(1, min(int(settings.PLAYBACK_URL_TTL_SECONDS), MAX_PLAYBACK_TTL_SECONDS))


def normalize_hostname(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "://" in value:
        raise ValueError("Expected a hostname without scheme or whitespace")
    if any(character in value for character in "/\\@:#?[]"):
        raise ValueError("Hostname must not contain credentials, port, path, query, or fragment")
    try:
        hostname = value.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValueError("Invalid hostname") from error
    if not hostname or len(hostname) > 253 or any(not HOST_LABEL.fullmatch(label) for label in hostname.split(".")):
        raise ValueError("Invalid hostname")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return hostname
    if not address.is_global:
        raise ValueError("Private and reserved IP hosts are forbidden")
    return hostname


def validate_provider_configuration(
    adapter_name: object,
    config: object,
    allowed_hosts: object,
) -> tuple[str, dict[str, object], list[str]]:
    if not isinstance(adapter_name, str):
        raise ValueError("Playback adapter must be a string")
    adapter = playback_adapters.get(adapter_name)
    if adapter is None:
        raise ValueError("Unknown or missing playback adapter")
    if not isinstance(config, dict):
        raise ValueError("Playback config must be an object")
    sensitive = SENSITIVE_CONFIG_KEYS.intersection(str(key).lower() for key in config)
    if sensitive:
        raise ValueError("Credentials and secrets must not be stored in playback config")
    if not isinstance(allowed_hosts, list) or not allowed_hosts:
        raise ValueError("At least one allowed hostname is required")
    normalized_hosts = [normalize_hostname(host) for host in allowed_hosts]
    if len(normalized_hosts) != len(set(normalized_hosts)):
        raise ValueError("Allowed hostnames must be unique")
    adapter.validate_config(config)
    return adapter_name, config, normalized_hosts


def source_url_allowed(source: Source) -> bool:
    if source.provider is None:
        return False
    try:
        _, _, allowed_hosts = validate_provider_configuration(
            source.provider.playback_adapter,
            source.provider.playback_config,
            source.provider.allowed_hosts,
        )
        parsed = urlsplit(source.url)
        hostname = normalize_hostname(parsed.hostname or "")
        port = parsed.port
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
        and not parsed.fragment
        and hostname in allowed_hosts
    )


def authorized_playback_source(source_id: int, *, now=None) -> Source | None:
    moment = now or timezone.now()
    source = Source.objects.select_related("provider").filter(
        pk=source_id,
        availability="available",
        provider__is_enabled=True,
    ).first()
    if source is None or not source_url_allowed(source):
        return None
    has_grant = RightsGrant.objects.filter(
        source=source,
        status=RightsGrant.Status.ACTIVE,
        valid_from__lte=moment,
        valid_until__gt=moment,
        approved_by__isnull=False,
        approved_at__isnull=False,
    ).exists()
    return source if has_grant else None


def issue_playback(source_id: int) -> PlaybackTarget | None:
    source = authorized_playback_source(source_id)
    if source is None or source.provider is None:
        return None
    adapter = playback_adapters.get(source.provider.playback_adapter)
    if adapter is None:
        return None
    ttl = playback_url_ttl()
    token = signing.dumps(
        {"source_id": source.pk, "adapter": adapter.name},
        salt=PLAYBACK_TOKEN_SALT,
        compress=True,
    )
    return PlaybackTarget(
        mode=adapter.name,
        url=reverse("source-playback-resolve", kwargs={"token": token}),
        expires_at=timezone.now() + timedelta(seconds=ttl),
    )


def resolve_playback(token: str) -> str | None:
    try:
        payload = signing.loads(token, salt=PLAYBACK_TOKEN_SALT, max_age=playback_url_ttl())
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict) or type(payload.get("source_id")) is not int or not isinstance(payload.get("adapter"), str):
        return None
    source = authorized_playback_source(payload["source_id"])
    if source is None or source.provider is None or source.provider.playback_adapter != payload["adapter"]:
        return None
    adapter = playback_adapters.get(payload["adapter"])
    if adapter is None:
        return None
    target = adapter.target_url(source)
    return target if source_url_allowed(source) and target == source.url else None
