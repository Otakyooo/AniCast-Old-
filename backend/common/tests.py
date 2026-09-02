import json
import logging
from datetime import timedelta
from typing import Any, cast
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone as dj_timezone
from rest_framework.test import APIClient
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from common import availability
from common.logging import JsonFormatter
from common.models import AvailabilitySample, DailyVisitStat
from common.security import constant_time_equals
from common.throttling import (
    AniCastAnonRateThrottle,
    AniCastUserRateThrottle,
    is_internal_safe_request,
)


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


@override_settings(INTERNAL_API_TOKEN="s" * 32)
def test_internal_api_token_only_marks_safe_matching_requests():
    factory = APIRequestFactory()
    safe = Request(factory.get("/api/v1/titles/", HTTP_X_ANICAST_INTERNAL_TOKEN="s" * 32))
    wrong = Request(factory.get("/api/v1/titles/", HTTP_X_ANICAST_INTERNAL_TOKEN="x" * 32))
    write = Request(factory.post("/api/v1/analytics/visit/", HTTP_X_ANICAST_INTERNAL_TOKEN="s" * 32))
    assert is_internal_safe_request(safe) is True
    assert is_internal_safe_request(wrong) is False
    assert is_internal_safe_request(write) is False
    throttle = AniCastAnonRateThrottle()
    assert throttle.allow_request(safe, object()) is True
    assert throttle.scope == "ssr"


@override_settings(INTERNAL_API_TOKEN="s" * 32)
def test_non_ascii_internal_token_is_rejected_without_raising():
    # Django decodes headers as latin-1, and hmac.compare_digest raises
    # TypeError on non-ASCII str. Comparing bytes keeps a hostile header a
    # plain mismatch instead of an unauthenticated 500 on every API request.
    factory = APIRequestFactory()
    request = Request(factory.get("/api/v1/titles/", HTTP_X_ANICAST_INTERNAL_TOKEN="é" * 32))
    assert is_internal_safe_request(request) is False


def test_constant_time_equals_fails_closed_on_unset_secret():
    assert constant_time_equals("", "") is False
    assert constant_time_equals("anything", "") is False
    assert constant_time_equals("secret", "secret") is True
    assert constant_time_equals("secret", "secrets") is False
    assert constant_time_equals("é", "secret") is False


@pytest.mark.django_db
@override_settings(METRICS_BEARER_TOKEN="test-metrics-token")
def test_metrics_reject_non_ascii_authorization_without_error():
    response = APIClient().get("/internal/metrics", HTTP_AUTHORIZATION="Bearer " + "é" * 20)
    assert response.status_code == 404


@pytest.mark.django_db
def test_authenticated_requests_are_throttled_per_account():
    # AnonRateThrottle returns None for logged-in callers, so without a user
    # bucket a single account could hammer the expensive personal endpoints.
    user = get_user_model().objects.create_user(
        email="rate@example.com", password="A-strong-passphrase-2042"
    )
    factory = APIRequestFactory()
    request = Request(factory.get("/api/v1/library/"))
    request.user = user

    throttle = AniCastUserRateThrottle()
    throttle.rate = "2/min"
    throttle.num_requests, throttle.duration = throttle.parse_rate(throttle.rate)
    assert throttle.allow_request(request, object()) is True
    assert throttle.allow_request(request, object()) is True
    assert throttle.allow_request(request, object()) is False


@pytest.mark.django_db
def test_user_throttle_leaves_anonymous_traffic_to_the_anon_bucket():
    factory = APIRequestFactory()
    request = Request(factory.get("/api/v1/titles/"))
    throttle = AniCastUserRateThrottle()
    assert throttle.get_cache_key(request, object()) is None


@pytest.mark.django_db
@override_settings(INTERNAL_API_TOKEN="s" * 32)
def test_user_throttle_exempts_trusted_ssr_requests():
    factory = APIRequestFactory()
    request = Request(factory.get("/api/v1/titles/", HTTP_X_ANICAST_INTERNAL_TOKEN="s" * 32))
    throttle = AniCastUserRateThrottle()
    throttle.rate = "1/min"
    throttle.num_requests, throttle.duration = throttle.parse_rate(throttle.rate)
    assert throttle.allow_request(request, object()) is True
    assert throttle.allow_request(request, object()) is True


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


@pytest.mark.django_db
def test_pending_migrations_are_exported_so_schema_drift_is_alertable():
    """A missed migration is only visible as 500s unless the cause is exported.

    A model referencing columns the schema lacks answers 500 on every request
    that touches them, which is what happened in production for an hour: the
    symptom alerted, the cause did not. The test database is migrated, so the
    healthy value is zero.
    """
    from common.metrics import render_metrics

    body = render_metrics()
    assert "# HELP anicast_pending_migrations" in body
    assert "# TYPE anicast_pending_migrations gauge" in body
    assert "anicast_pending_migrations 0" in body


# ---------- Anonymous visit counter ----------


@pytest.mark.django_db
def test_visit_counter_counts_browser_once_per_day():
    client = APIClient()
    first = client.post("/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0 AniCast test")
    second = client.post("/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0 AniCast test")

    assert first.status_code == 200
    assert first.json() == {"total": 1, "today": 1, "counted": True}
    assert first.cookies["anicast_visit_day"]["httponly"] is True
    assert first.cookies["anicast_visit_day"]["samesite"] == "Lax"
    assert second.json() == {"total": 1, "today": 1, "counted": False}
    assert DailyVisitStat.objects.get().visits == 1


@pytest.mark.django_db
def test_visit_counter_counts_a_second_browser():
    first = APIClient()
    second = APIClient()
    first.post("/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0 browser one")
    response = second.post("/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0 browser two")

    assert response.json() == {"total": 2, "today": 2, "counted": True}
    assert DailyVisitStat.objects.get().visits == 2


@pytest.mark.django_db
@pytest.mark.parametrize("user_agent", ["Googlebot/2.1", "Blackbox monitoring", "curl/8.0", ""])
def test_visit_counter_ignores_automated_clients(user_agent):
    response = APIClient().post("/api/v1/analytics/visit/", HTTP_USER_AGENT=user_agent)

    assert response.json() == {"total": 0, "today": 0, "counted": False}
    assert "anicast_visit_day" not in response.cookies
    assert not DailyVisitStat.objects.exists()


@pytest.mark.django_db
def test_visit_counter_recovers_from_invalid_cookie_without_storing_identifiers():
    client = APIClient()
    client.cookies["anicast_visit_day"] = "tampered"
    response = client.post(
        "/api/v1/analytics/visit/",
        HTTP_USER_AGENT="Mozilla/5.0",
        REMOTE_ADDR="203.0.113.42",
    )

    assert response.json()["counted"] is True
    field_names = {field.name for field in DailyVisitStat._meta.fields}
    assert field_names == {"id", "day", "visits", "created_at", "updated_at"}
    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_visit_counter_is_exported_as_aggregate_metrics():
    DailyVisitStat.objects.create(day=dj_timezone.localdate(), visits=7)
    from common.metrics import render_metrics

    body = render_metrics()
    assert 'anicast_site_visits{period="today"} 7' in body
    assert 'anicast_site_visits{period="total"} 7' in body


@pytest.mark.django_db
def test_visit_counter_requires_csrf_for_real_http_clients():
    client = APIClient(enforce_csrf_checks=True)
    assert client.post("/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0").status_code == 403
    token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    response = client.post(
        "/api/v1/analytics/visit/",
        HTTP_USER_AGENT="Mozilla/5.0",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    assert response.json()["counted"] is True


def visit_rate(rate: str) -> dict[str, Any]:
    """REST_FRAMEWORK override that changes only the visit bucket.

    ``settings.REST_FRAMEWORK`` is typed as ``object``, so the mapping is read
    through an explicit cast instead of being unpacked directly.
    """
    framework = cast(dict[str, Any], settings.REST_FRAMEWORK)
    rates = cast(dict[str, str], framework["DEFAULT_THROTTLE_RATES"])
    return {**framework, "DEFAULT_THROTTLE_RATES": {**rates, "visit": rate}}


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=visit_rate("2/hour"))
def test_visit_counter_stops_counting_beyond_the_per_address_budget():
    # The bot check reads the User-Agent and the dedupe check reads a cookie the
    # client controls, so a script that discards cookies must still be bounded:
    # every counted request takes a row lock on today's counter. Exhausting the
    # budget only stops counting — the response stays a normal 200 summary.
    client = APIClient()
    for _ in range(2):
        response = client.post(
            "/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0", REMOTE_ADDR="203.0.113.7"
        )
        assert response.json()["counted"] is True
        client.cookies.clear()

    throttled = client.post(
        "/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0", REMOTE_ADDR="203.0.113.7"
    )
    assert throttled.status_code == 200
    assert throttled.json() == {"total": 2, "today": 2, "counted": False}
    assert "anicast_visit_day" not in throttled.cookies
    assert DailyVisitStat.objects.get().visits == 2

    other_address = APIClient().post(
        "/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0", REMOTE_ADDR="198.51.100.9"
    )
    assert other_address.json()["counted"] is True


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=visit_rate("1/hour"))
def test_visit_budget_is_only_spent_by_counted_visits():
    # A returning browser sends its signed cookie, so repeat page loads must not
    # consume the bucket that protects the counter from cookie-less clients.
    client = APIClient()
    assert client.post(
        "/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0", REMOTE_ADDR="203.0.113.8"
    ).json()["counted"] is True
    for _ in range(5):
        repeat = client.post(
            "/api/v1/analytics/visit/", HTTP_USER_AGENT="Mozilla/5.0", REMOTE_ADDR="203.0.113.8"
        )
        assert repeat.status_code == 200
        assert repeat.json() == {"total": 1, "today": 1, "counted": False}


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=visit_rate("1/hour"))
def test_visit_throttle_trusts_only_the_address_the_proxy_appended():
    # Caddy appends the peer address to any inbound X-Forwarded-For. With
    # NUM_PROXIES=1 only that last hop counts, so a client-supplied prefix
    # cannot mint a fresh bucket per request.
    first = APIClient()
    assert first.post(
        "/api/v1/analytics/visit/",
        HTTP_USER_AGENT="Mozilla/5.0",
        HTTP_X_FORWARDED_FOR="10.0.0.1, 203.0.113.9",
        REMOTE_ADDR="127.0.0.1",
    ).json()["counted"] is True

    spoofed = APIClient()
    throttled = spoofed.post(
        "/api/v1/analytics/visit/",
        HTTP_USER_AGENT="Mozilla/5.0",
        HTTP_X_FORWARDED_FOR="10.9.9.9, 203.0.113.9",
        REMOTE_ADDR="127.0.0.1",
    )
    assert throttled.json()["counted"] is False
    assert DailyVisitStat.objects.get().visits == 1


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
def test_availability_samples_use_bounded_aggregate_queries(django_assert_num_queries):
    now = dj_timezone.now()
    for minutes in range(120):
        _sample("site", now - timedelta(minutes=minutes), minutes % 7 != 0)
    _sample("api", now - timedelta(days=2), True)
    with django_assert_num_queries(2):
        up, uptime = availability.availability_samples()
    assert up == ['anicast_availability_up{target="site"} 0']
    assert uptime[0].startswith('anicast_availability_uptime_percent{target="site"} ')
    assert all('target="api"' not in sample for sample in [*up, *uptime])


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


@pytest.mark.django_db
def test_summarize_reports_latency_and_probe_counts():
    now = dj_timezone.now()
    _sample("site", now - timedelta(minutes=10), True, latency_ms=100)
    _sample("site", now - timedelta(minutes=5), True, latency_ms=300)

    summary = availability.summarize("site", now=now)
    assert summary["avg_latency_ms"] == 200
    assert summary["samples_24h"] == 2
    assert summary["last_checked_at"] == now - timedelta(minutes=5)


@pytest.mark.django_db
def test_dashboard_rows_link_to_filtered_samples():
    now = dj_timezone.now()
    _sample("site", now, True, latency_ms=120)
    _sample("api", now - timedelta(hours=30), True, latency_ms=400)

    rows = availability.build_availability_dashboard(now=now)
    site_row = next(row for row in rows if row["label"] == "Сайт")
    api_row = next(row for row in rows if row["label"] == "API каталога")
    assert site_row["url"] == "/staff/common/availabilitysample/?target__exact=site"
    assert "~120 мс" in site_row["checked_line"]
    assert "проб за 24ч: 1" in site_row["checked_line"]
    # The 30-hour-old api sample is outside the 24h window: no latency line.
    assert "~400 мс" not in api_row["checked_line"]


@pytest.mark.django_db
def test_system_cards_surface_background_failures():
    from common import staff_dashboard

    fake_tasks = ("task.a", "task.b")

    def fake_value(metric, *labels):
        if metric == "celery_tasks":
            if labels == ("task.a", "failure"):
                return 2
            if labels == ("task.b", "retry"):
                return 1
            return 0
        if metric == "notification_deliveries":
            return 3
        return 0

    with patch("common.metrics.TASKS", fake_tasks), patch(
        "common.metrics.value", side_effect=fake_value
    ):
        cards = staff_dashboard._system_cards()

    tasks_card, delivery_card = cards
    assert tasks_card["value"] == 2
    assert tasks_card["tone"] == "danger"
    assert tasks_card["url"] == ""
    assert "повторы: 1" in tasks_card["hint"]
    assert delivery_card["value"] == 3
    assert delivery_card["tone"] == "warn"
    assert "telegramnotificationchannel" in delivery_card["url"]

    with patch("common.metrics.TASKS", fake_tasks), patch("common.metrics.value", return_value=0):
        quiet = staff_dashboard._system_cards()
    assert all(card["tone"] == "ok" and card["url"] == "" for card in quiet)


@pytest.mark.django_db
def test_staff_index_renders_availability_section():
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_superuser("staff@example.com", "Sup3rSecret!42")
    client = APIClient()
    client.force_login(user)
    response = client.get("/staff/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Доступность" in body
    assert "Работает" in body or "Нет данных" in body
    assert "Сводка редактора" in body
    # Admin theme is applied on every /staff/ page via base_site override.
    assert "anicast-theme" in body
    assert "--primary: #7c5cff" in body
