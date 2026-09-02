import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from catalog.health import HealthResult, check_source
from catalog.models import Episode, Provider, Source, SourceHealthCheck, Title
from catalog.tasks import check_provider_sources


@pytest.fixture
def monitored_source(db):
    provider = Provider.objects.create(
        name="Health Provider",
        slug="health-provider",
        is_enabled=True,
        allowed_hosts=["watch.example.com"],
        playback_adapter="external_link",
    )
    title = Title.objects.create(name="Health Title", slug="health-title")
    episode = Episode.objects.create(title=title, number=1)
    return Source.objects.create(
        episode=episode, provider=provider, name="Health Source", url="https://watch.example.com/episode/1"
    )


@pytest.mark.django_db
def test_health_check_rejects_private_dns(monitored_source):
    def resolver(*args, **kwargs):
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    result = check_source(monitored_source, resolver=resolver)
    assert result.is_healthy is False
    assert result.error == "private_destination"


@pytest.mark.django_db
def test_health_check_accepts_allowlisted_public_destination(monitored_source):
    def resolver(*args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    class Response:
        status = 204

        def close(self):
            pass

    class Opener:
        def open(self, request, timeout):
            return Response()

    result = check_source(monitored_source, resolver=resolver, opener=Opener())
    assert result.is_healthy is True
    assert result.http_status == 204


@pytest.mark.django_db
def test_task_marks_three_failures_and_recovers_automatic_error(monitored_source, monkeypatch):
    monkeypatch.setattr("catalog.tasks.check_source", lambda source: HealthResult(False, None, 5, "timeout"))
    for _ in range(3):
        check_provider_sources()
    monitored_source.refresh_from_db()
    assert monitored_source.availability == "provider_error"
    assert monitored_source.consecutive_failures == 3
    assert SourceHealthCheck.objects.filter(source=monitored_source).count() == 3
    monkeypatch.setattr("catalog.tasks.check_source", lambda source: HealthResult(True, 200, 3))
    check_provider_sources()
    monitored_source.refresh_from_db()
    assert monitored_source.availability == "available"
    assert monitored_source.consecutive_failures == 0


@pytest.mark.django_db
def test_provider_check_walks_the_catalog_across_runs(monitored_source, monkeypatch):
    """A run probes a bounded slice; the cursor covers the rest next time.

    The pass previously walked every enabled source in one task. At the current
    catalog size (~29k sources, 10s HEAD timeout each) that cannot finish inside
    the Celery soft limit, so the run was killed mid-batch and the tail of the
    catalog was never checked.
    """
    provider = monitored_source.provider
    title = monitored_source.episode.title
    for number in range(2, 8):
        episode = Episode.objects.create(title=title, number=number)
        Source.objects.create(
            episode=episode,
            provider=provider,
            external_id=f"episode-{number}",
            name="Health Source",
            url=f"https://watch.example.com/episode/{number}",
        )
    probed: list[int] = []

    def record(source):
        probed.append(source.pk)
        return HealthResult(True, 200, 3)

    monkeypatch.setattr("catalog.tasks.check_source", record)

    first = check_provider_sources(limit=3)
    assert first["checked"] == 3
    second = check_provider_sources(limit=3)
    assert second["checked"] == 3
    # Distinct slices, in id order, with no source probed twice in one sweep.
    assert len(set(probed)) == 6
    assert probed == sorted(probed)

    all_ids = list(Source.objects.order_by("id").values_list("id", flat=True))
    assert probed == all_ids[:6]

    # The cursor wraps once the catalog is exhausted, so checking never stalls.
    third = check_provider_sources(limit=3)
    assert third["checked"] == 1
    fourth = check_provider_sources(limit=3)
    assert fourth["checked"] == 3
    assert probed[6:] == all_ids[6:] + all_ids[:3]


@pytest.mark.django_db
def test_provider_check_stops_probing_at_its_time_budget(monitored_source, monkeypatch):
    """The wall-clock budget must stop new probes before the soft limit fires."""
    provider = monitored_source.provider
    title = monitored_source.episode.title
    for number in range(2, 6):
        episode = Episode.objects.create(title=title, number=number)
        Source.objects.create(
            episode=episode,
            provider=provider,
            external_id=f"budget-{number}",
            name="Health Source",
            url=f"https://watch.example.com/episode/{number}",
        )
    calls: list[int] = []

    def record(source):
        calls.append(source.pk)
        return HealthResult(True, 200, 3)

    monkeypatch.setattr("catalog.tasks.check_source", record)
    # Two probes fit, then the deadline has passed: monotonic advances by one
    # budget per call, and the loop checks it before each probe.
    ticks = iter([0.0, 1.0, 2.0, 1e9, 1e9, 1e9])
    monkeypatch.setattr("catalog.tasks.time.monotonic", lambda: next(ticks))

    result = check_provider_sources(limit=5)
    assert result["checked"] == 2
    assert len(calls) == 2
    # Only the probed rows are written, and the cursor resumes from there.
    assert SourceHealthCheck.objects.count() == 2
    assert Source.objects.filter(last_checked_at__isnull=False).count() == 2


@pytest.mark.django_db
def test_provider_check_prunes_health_history(monitored_source, monkeypatch):
    """The ledger grows by one row per source per run, so it needs retention.

    Two weeks covers the rolling windows the staff dashboard renders; older rows
    only consume space.
    """
    from datetime import timedelta

    from django.utils import timezone

    from catalog.tasks import HEALTH_CHECK_RETENTION_DAYS

    stale = SourceHealthCheck.objects.create(source=monitored_source, is_healthy=True, http_status=200)
    recent = SourceHealthCheck.objects.create(source=monitored_source, is_healthy=True, http_status=200)
    now = timezone.now()
    SourceHealthCheck.objects.filter(pk=stale.pk).update(
        checked_at=now - timedelta(days=HEALTH_CHECK_RETENTION_DAYS + 1)
    )
    SourceHealthCheck.objects.filter(pk=recent.pk).update(
        checked_at=now - timedelta(days=HEALTH_CHECK_RETENTION_DAYS - 1)
    )

    monkeypatch.setattr("catalog.tasks.check_source", lambda source: HealthResult(True, 200, 3))
    result = check_provider_sources()

    assert result["pruned"] == 1
    assert not SourceHealthCheck.objects.filter(pk=stale.pk).exists()
    assert SourceHealthCheck.objects.filter(pk=recent.pk).exists()


@pytest.mark.django_db
def test_task_skips_browser_only_iframe_sources(monitored_source, monkeypatch):
    monitored_source.provider.playback_adapter = "iframe_embed"
    monitored_source.provider.save(update_fields=["playback_adapter"])
    monkeypatch.setattr(
        "catalog.tasks.check_source",
        lambda source: pytest.fail("iframe source must not be checked from the backend"),
    )

    assert check_provider_sources() == {"checked": 0, "failed": 0, "pruned": 0}
    assert not SourceHealthCheck.objects.filter(source=monitored_source).exists()


@pytest.mark.django_db
def test_health_error_does_not_persist_source_url(monitored_source, monkeypatch):
    secret_url = "https://watch.example.com/episode/1?token=must-not-leak"
    monitored_source.url = secret_url
    monitored_source.save(update_fields=["url"])
    monkeypatch.setattr("catalog.tasks.check_source", lambda source: HealthResult(False, None, 5, "network_error"))
    check_provider_sources()
    check = SourceHealthCheck.objects.get(source=monitored_source)
    assert check.error == "network_error"
    assert secret_url not in check.error


def import_payload():
    return {
        "genres": [{"name": "Import Genre", "slug": "import-genre"}],
        "franchises": [{"name": "Import Franchise", "slug": "import-franchise"}],
        "providers": [{
            "name": "Import Provider",
            "slug": "import-provider",
            "allowed_hosts": ["video.example.com"],
            "playback_adapter": "external_link",
        }],
        "titles": [{
            "name": "Import Title", "slug": "import-title", "genres": ["import-genre"], "franchise": "import-franchise",
            "translations": {"ru": {"name": "Импортированный тайтл", "synopsis": "Описание"}},
            "episodes": [{"number": 1, "air_date": "2026-08-21", "sources": [{"provider": "import-provider", "name": "Import Source", "url": "https://video.example.com/1"}]}],
        }],
    }


@pytest.mark.django_db
def test_import_catalog_dry_run_rolls_back_and_apply_persists(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(import_payload()), encoding="utf-8")
    output = StringIO()
    call_command("import_catalog", path, stdout=output)
    assert "DRY-RUN" in output.getvalue()
    assert not Title.objects.filter(slug="import-title").exists()
    call_command("import_catalog", path, apply=True, stdout=output)
    title = Title.objects.get(slug="import-title")
    assert title.episodes.get(number=1).sources.get().provider.is_enabled is False
    assert title.episodes.get(number=1).sources.get().provider.playback_adapter == "external_link"
    assert title.translations.get(language="ru").name == "Импортированный тайтл"


@pytest.mark.django_db
def test_import_catalog_reads_air_at_and_rejects_naive_or_invalid_values(tmp_path):
    payload = import_payload()
    payload["titles"][0]["episodes"][0]["air_at"] = "2026-08-21T18:30:00+03:00"
    path = tmp_path / "air-at.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    call_command("import_catalog", path, apply=True)
    episode = Title.objects.get(slug="import-title").episodes.get(number=1)
    assert episode.air_at is not None
    assert episode.air_date is not None

    payload["titles"][0]["episodes"][0]["air_at"] = "2026-08-21T18:30:00"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError, match="часового пояса"):
        call_command("import_catalog", path, apply=True)

    payload["titles"][0]["episodes"][0]["air_at"] = "not-a-datetime"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError, match="неверная air_at"):
        call_command("import_catalog", path, apply=True)


@pytest.mark.django_db
def test_import_catalog_rejects_http_source(tmp_path):
    payload = import_payload()
    payload["titles"][0]["episodes"][0]["sources"][0]["url"] = "http://127.0.0.1/private"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError, match="HTTPS"):
        call_command("import_catalog", path, apply=True)
    assert not Title.objects.filter(slug="import-title").exists()


@pytest.mark.django_db
def test_import_catalog_rejects_unknown_adapter_and_host_mismatch(tmp_path):
    payload = import_payload()
    payload["providers"][0]["playback_adapter"] = "unknown"
    path = tmp_path / "unknown-adapter.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError, match="Unknown"):
        call_command("import_catalog", path, apply=True)

    payload = import_payload()
    payload["titles"][0]["episodes"][0]["sources"][0]["url"] = "https://evil.example.com/1"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError, match="allowlist"):
        call_command("import_catalog", path, apply=True)
