"""The metadata provider's address must be configuration, not a constant."""

import pathlib

from django.conf import settings
from django.test import override_settings

from catalog import portraits, posters, providers

PROVIDER_DOMAINS = ("shikimori.io", "shikimori.one", "shikimori.org", "shikimori.me")


def test_default_base_is_the_live_domain():
    assert providers.base_url() == "https://shikimori.io"
    assert providers.api_base() == "https://shikimori.io/api"
    assert providers.graphql_url() == "https://shikimori.io/api/graphql"


@override_settings(METADATA_BASE_URL="https://example.test")
def test_every_derived_url_follows_the_configured_base():
    assert providers.api_base() == "https://example.test/api"
    assert providers.graphql_url() == "https://example.test/api/graphql"
    assert providers.absolute_url("/system/animes/original/21.jpg") == (
        "https://example.test/system/animes/original/21.jpg"
    )


def test_absolute_url_passes_absolute_urls_through():
    for value in ("https://cdn.myanimelist.net/images/x.jpg", "http://example.test/a.jpg"):
        assert providers.absolute_url(value) == value
    assert providers.absolute_url("") == ""


@override_settings(METADATA_BASE_URL="https://moved.test", METADATA_ASSET_HOSTS=("retired.test",))
def test_asset_hosts_accept_the_configured_host_and_every_alias():
    hosts = providers.asset_hosts()
    assert "moved.test" in hosts
    assert "retired.test" in hosts
    assert providers.is_asset_url("https://moved.test/system/animes/original/21.jpg")
    assert providers.is_asset_url("https://retired.test/a.jpg")
    assert not providers.is_asset_url("http://moved.test/a.jpg")
    assert not providers.is_asset_url("https://evil.test/a.jpg")


def test_retired_aliases_stay_valid_for_stored_artwork():
    """Rows written before a domain move must not become untrusted.

    shikimori.one now answers 301/308 to shikimori.io, but the origins recorded
    back when it was live are still the only handle we have on that artwork.
    """
    assert {"shikimori.io", "shikimori.one"} <= providers.asset_hosts()
    assert providers.is_asset_url("https://shikimori.one/system/animes/original/21.jpg")
    assert "shikimori.one" in portraits.ALLOWED_ORIGIN_HOSTS
    assert "shikimori.one" in posters.ALLOWED_POSTER_HOSTS


def test_allowlists_are_derived_from_the_provider_hosts():
    assert posters.ALLOWED_POSTER_HOSTS == providers.asset_hosts() | frozenset(
        {"cdn.myanimelist.net", "media.kitsu.app", "media.kitsu.io"}
    )
    assert portraits.ALLOWED_ORIGIN_HOSTS == providers.asset_hosts() | frozenset({"cdn.myanimelist.net"})


def test_provider_domain_is_named_in_exactly_one_place():
    """Guard the decoupling: the address lives in settings and providers only.

    A new hardcoded domain would silently reintroduce the coupling this change
    removed, and would not follow a future move. Historical migrations are
    exempt — they record what was true when they ran.
    """
    backend = pathlib.Path(settings.BASE_DIR)
    allowed = {"settings.py", "providers.py"}
    offenders: list[str] = []
    for path in sorted(backend.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
        if "migrations" in path.parts or path.name in allowed or path.name.startswith("test"):
            continue
        text = path.read_text(encoding="utf-8")
        for domain in PROVIDER_DOMAINS:
            if domain in text:
                offenders.append(f"{path.relative_to(backend)}: {domain}")
    assert offenders == [], f"hardcoded provider domains: {offenders}"
