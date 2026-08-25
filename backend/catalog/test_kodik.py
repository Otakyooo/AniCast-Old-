from io import StringIO

import pytest
from django.core.management import call_command

from catalog.kodik import KodikSearchResult, normalize_player_url, player_url_allowed
from catalog.models import Episode, Provider, RightsGrant, Source, Title


def kodik_result():
    return {
        "id": "serial-1",
        "translation": {"id": 610, "title": "AniLibria.TV", "type": "voice"},
        "seasons": {
            "1": {
                "episodes": {
                    "1": {"link": "https://kodikplayer.com/seria/1/redacted-one/720p"},
                    "2": {"link": "https://kodikplayer.com/seria/2/redacted-two/720p"},
                    "3": {"link": "https://evil.example/seria/3/redacted/720p"},
                }
            }
        },
    }


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://kodikplayer.com/seria/1/hash/720p", True),
        ("http://kodikplayer.com/seria/1/hash/720p", False),
        ("https://evil.example/seria/1/hash/720p", False),
        ("https://user:pass@kodikplayer.com/seria/1/hash/720p", False),
        ("https://kodikplayer.com:444/seria/1/hash/720p", False),
        ("https://kodikplayer.com/seria/1/hash/720p#fragment", False),
        ("https://kodikplayer.com/account/settings", False),
    ],
)
def test_player_url_allowed(url, expected):
    assert player_url_allowed(url) is expected


def test_normalize_player_url_upgrades_protocol_relative_links():
    assert normalize_player_url("//kodikplayer.com/seria/1/hash/720p") == "https://kodikplayer.com/seria/1/hash/720p"
    assert normalize_player_url("//evil.example/seria/1/hash/720p") is None


@pytest.mark.django_db
def test_sync_kodik_is_dry_run_first_and_keeps_rights_manual(monkeypatch):
    title = Title.objects.create(name="Attack", slug="16498-shingeki-no-kyojin")
    Episode.objects.create(title=title, number=1)
    Episode.objects.create(title=title, number=2)
    monkeypatch.setattr(
        "catalog.management.commands.sync_kodik.search_by_shikimori",
        lambda shikimori_id, **kwargs: KodikSearchResult(total=1, results=[kodik_result()]),
    )

    dry_output = StringIO()
    call_command("sync_kodik", title.slug, stdout=dry_output)
    assert "DRY-RUN" in dry_output.getvalue()
    assert Provider.objects.filter(slug="kodik").exists() is False
    assert Source.objects.filter(episode__title=title).exists() is False

    apply_output = StringIO()
    call_command("sync_kodik", title.slug, apply=True, stdout=apply_output)
    assert "APPLIED" in apply_output.getvalue()
    provider = Provider.objects.get(slug="kodik")
    assert provider.is_enabled is False
    assert provider.playback_adapter == "iframe_embed"
    assert provider.allowed_hosts == ["kodikplayer.com"]
    sources = list(Source.objects.filter(episode__title=title).order_by("episode__number"))
    assert [source.episode.number for source in sources] == [1, 2]
    assert all(source.provider == provider for source in sources)
    assert all(source.external_id == "serial-1:s1:t610" for source in sources)
    assert RightsGrant.objects.filter(source__in=sources).exists() is False

    renamed = kodik_result()
    renamed["translation"] = {"id": 610, "title": "AniLibria Renamed", "type": "voice"}
    renamed["seasons"]["1"]["episodes"].pop("2")
    monkeypatch.setattr(
        "catalog.management.commands.sync_kodik.search_by_shikimori",
        lambda shikimori_id, **kwargs: KodikSearchResult(total=1, results=[renamed]),
    )
    call_command("sync_kodik", title.slug, apply=True, stdout=StringIO())
    sources = list(Source.objects.filter(episode__title=title).order_by("episode__number"))
    assert len(sources) == 2
    assert sources[0].name == "Kodik · AniLibria Renamed"
    assert sources[0].availability == "available"
    assert sources[1].availability == "unavailable"
    assert sources[1].availability_reason == "Kodik sync: source no longer returned"

    sources[1].availability = "available"
    sources[1].save(update_fields=["availability"])
    monkeypatch.setattr(
        "catalog.management.commands.sync_kodik.search_by_shikimori",
        lambda shikimori_id, **kwargs: KodikSearchResult(total=2, results=[renamed]),
    )
    call_command("sync_kodik", title.slug, apply=True, limit=1, stdout=StringIO())
    sources[1].refresh_from_db()
    assert sources[1].availability == "available"

    monkeypatch.setattr(
        "catalog.management.commands.sync_kodik.search_by_shikimori",
        lambda shikimori_id, **kwargs: KodikSearchResult(total=0, results=[]),
    )
    call_command("sync_kodik", title.slug, apply=True, stdout=StringIO())
    assert not Source.objects.filter(episode__title=title, availability="available").exists()
