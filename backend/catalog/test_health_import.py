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
        name="Health Provider", slug="health-provider", is_enabled=True, allowed_hosts=["watch.example.com"]
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
        "providers": [{"name": "Import Provider", "slug": "import-provider", "allowed_hosts": ["video.example.com"]}],
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
    assert title.translations.get(language="ru").name == "Импортированный тайтл"


@pytest.mark.django_db
def test_import_catalog_rejects_http_source(tmp_path):
    payload = import_payload()
    payload["titles"][0]["episodes"][0]["sources"][0]["url"] = "http://127.0.0.1/private"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError, match="HTTPS"):
        call_command("import_catalog", path, apply=True)
    assert not Title.objects.filter(slug="import-title").exists()
