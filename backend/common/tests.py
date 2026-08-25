import json
import logging
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone as dj_timezone
from rest_framework.test import APIClient

from common import availability
from common.logging import JsonFormatter
from common.models import AvailabilitySample


@pytest.mark.django_db
def test_live_health_does_not_require_database():
    response = APIClient().get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response["X-Request-ID"]


@pytest.mark.django_db
def test_ready_health_reports_database():
    response = APIClient().get("/health/ready")
    assert response.status_code == 200
    assert response.json()["dependencies"]["database"] == "ok"


@pytest.mark.django_db
def test_ready_health_reports_each_failed_dependency():
    with patch("common.views.connection.cursor", side_effect=RuntimeError("database-secret")):
        response = APIClient().get("/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"] == {"database": "unavailable", "cache": "ok"}
    assert "database-secret" not in response.content.decode()


@pytest.mark.django_db
def test_request_id_is_validated_and_propagated():
    client = APIClient()
    assert client.get("/health/live", HTTP_X_REQUEST_ID="valid-id")["X-Request-ID"] == "valid-id"
    generated = client.get("/health/live", HTTP_X_REQUEST_ID="bad id with spaces")["X-Request-ID"]
    assert generated != "bad id with spaces"
    assert len(generated) == 32


@pytest.mark.django_db
@override_settings(METRICS_BEARER_TOKEN="test-metrics-token")
def test_metrics_are_private_and_prometheus_compatible():
    client = APIClient()
    assert client.get("/internal/metrics").status_code == 404
    assert client.get("/internal/metrics", HTTP_AUTHORIZATION="Bearer wrong").status_code == 404
    response = client.get("/internal/metrics", HTTP_AUTHORIZATION="Bearer test-metrics-token")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert "text/plain" in response["Content-Type"]
    body = response.content.decode()
    assert "anicast_http_requests_total" in body
    assert "test-metrics-token" not in body


def test_json_formatter_uses_allowlist_and_omits_message():
    record = logging.LogRecord("anicast.request", logging.INFO, __file__, 1, "token=secret", (), None)
    record.event = "http_request_completed"
    record.authorization = "Bearer secret"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "http_request_completed"
    assert "secret" not in json.dumps(payload)
    assert "message" not in payload


# ---------- Availability tracking ----------


def _sample(target, checked_at, ok, latency_ms=42):
    return AvailabilitySample.objects.create(
        target=target,
        checked_at=checked_at,
        ok=ok,
        latency_ms=latency_ms,
        status_code=200 if ok else 502,
    )


@pytest.mark.django_db
def test_probe_all_records_every_target_and_prunes():
    now = dj_timezone.now()
    stale = AvailabilitySample.objects.create(
        target="site",
        checked_at=now - timedelta(days=availability.RETENTION_DAYS + 1),
        ok=True,
    )
    fake_targets = (
        availability.Target("site", "Сайт", "http://probe/site", {}),
        availability.Target("api", "API", "http://probe/api", {}),
        availability.Target("readiness", "Readiness", "http://probe/ready", {}),
    )
    with patch.object(availability, "_targets", lambda: fake_targets):
        with patch.object(
            availability,
            "probe_target",
            side_effect=[
                {"ok": True, "latency_ms": 11, "status_code": 200, "detail": ""},
                {"ok": True, "latency_ms": 12, "status_code": 200, "detail": ""},
                {"ok": False, "latency_ms": 13, "status_code": None, "detail": "timeout"},
            ],
        ):
            outcomes = availability.probe_all()
    assert outcomes == {"site": True, "api": True, "readiness": False}
    availability.prune()
    assert not AvailabilitySample.objects.filter(pk=stale.pk).exists()
    fresh = set(
        AvailabilitySample.objects.filter(checked_at__gte=now - timedelta(minutes=1))
        .values_list("target", flat=True)
    )
    assert fresh == {"site", "api", "readiness"}


@pytest.mark.django_db
def test_summarize_uptime_windows_streak_and_incident():
    now = dj_timezone.now()
    _sample("api", now - timedelta(days=6), True)
    _sample("api", now - timedelta(days=2, minutes=3), False)
    _sample("api", now - timedelta(days=2, minutes=2), False)
    _sample("api", now - timedelta(days=2, minutes=1), True)
    _sample("api", now - timedelta(minutes=21), True)
    _sample("api", now - timedelta(minutes=20), False)
    _sample("api", now - timedelta(minutes=19), True)

    summary = availability.summarize("api", now=now)
    assert summary["currently_up"] is True
    # 24h window: three samples (21/20/19 minutes ago), one failed.
    assert summary["uptime_24h"] == f"{100.0 * 2 / 3:.2f}%"
    # 7d window: all seven samples including the two-day-old outage.
    assert summary["uptime_7d"] == f"{100.0 * 4 / 7:.2f}%"
    assert summary["streak_started"] == now - timedelta(minutes=19)
    assert summary["last_incident"] == now - timedelta(minutes=20)


@pytest.mark.django_db
def test_summarize_reports_downtime_in_progress():
    now = dj_timezone.now()
    _sample("site", now - timedelta(minutes=30), True)
    _sample("site", now - timedelta(minutes=5), False)

    summary = availability.summarize("site", now=now)
    assert summary["currently_up"] is False
    assert summary["last_incident"] is None
    assert "недоступен с" in summary["detail_line"]


@pytest.mark.django_db
def test_summarize_streak_counts_from_first_sample_without_outages():
    now = dj_timezone.now()
    _sample("site", now - timedelta(days=3), True)
    _sample("site", now - timedelta(minutes=1), True)

    summary = availability.summarize("site", now=now)
    assert summary["currently_up"] is True
    assert summary["streak_started"] == now - timedelta(days=3)
    assert summary["last_incident"] is None


@pytest.mark.django_db
def test_summarize_without_samples_degrades_cleanly():
    summary = availability.summarize("readiness")
    assert summary["currently_up"] is False
    assert summary["uptime_24h"] == "—"
    assert summary["uptime_7d"] == "—"


@pytest.mark.django_db
def test_dashboard_rows_shape():
    now = dj_timezone.now()
    _sample("site", now, True)
    rows = availability.build_availability_dashboard(now=now)
    site_row = next(row for row in rows if row["label"] == "Сайт")
    api_row = next(row for row in rows if row["label"] == "API каталога")
    assert site_row["status_label"] == "Работает"
    assert site_row["tone"] == "ok"
    assert api_row["status_label"] == "Нет данных"
    assert api_row["tone"] == "warn"


@pytest.mark.django_db
def test_availability_metrics_render_prometheus_families():
    from common.metrics import render_metrics

    now = dj_timezone.now()
    _sample("site", now, True)
    body = render_metrics()
    assert "# HELP anicast_availability_up" in body
    assert 'anicast_availability_up{target="site"} 1' in body
    assert "# HELP anicast_availability_uptime_percent" in body


@pytest.mark.django_db
def test_beat_task_persists_samples_for_every_target():
    from common.tasks import probe_site_availability

    fake_targets = (
        availability.Target("site", "Сайт", "http://probe/site", {}),
        availability.Target("api", "API", "http://probe/api", {}),
        availability.Target("readiness", "Readiness", "http://probe/ready", {}),
    )
    with patch.object(availability, "_targets", lambda: fake_targets):
        with patch.object(
            availability,
            "probe_target",
            return_value={"ok": True, "latency_ms": 9, "status_code": 200, "detail": ""},
        ):
            probe_site_availability.run()
    assert AvailabilitySample.objects.count() == 3
