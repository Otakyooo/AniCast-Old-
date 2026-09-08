from unittest.mock import patch

import pytest
from django.core.cache import caches
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from common import metrics
from common.throttling import AniCastAnonRateThrottle


@pytest.fixture(autouse=True)
def reset_telemetry_backoff():
    with patch.object(metrics, "_cache_retry_at", 0):
        yield


def test_disposable_cache_clear_preserves_throttle_and_task_lock():
    request = Request(APIRequestFactory().get("/api/v1/titles/"))
    throttle = AniCastAnonRateThrottle()
    throttle.num_requests, throttle.duration = 1, 60
    assert throttle.allow_request(request, object())
    assert caches["default"].add("catalog:poster-refresh-lock", "held", 60)
    metrics.increment("isolation-test")
    assert metrics.value("isolation-test") == 1
    caches["ephemeral"].clear()
    assert metrics.value("isolation-test") == 0
    assert not throttle.allow_request(request, object())
    assert not caches["default"].add("catalog:poster-refresh-lock", "other", 60)


@pytest.mark.django_db
def test_telemetry_outage_keeps_api_and_readiness_available():
    with patch.object(caches["ephemeral"], "add", side_effect=ConnectionError("private-url")) as add:
        client = APIClient()
        assert client.get("/api/v1/titles/").status_code == 200
        assert client.get("/health/ready").status_code == 200
        # Subsequent metric operations back off instead of multiplying timeouts.
        metrics.increment("isolation-test")
        assert metrics.value("isolation-test") == 0
        assert add.call_count == 1


def test_telemetry_recovers_after_backoff():
    with patch("common.metrics.monotonic", return_value=10), patch.object(
        caches["ephemeral"], "add", side_effect=ConnectionError
    ):
        metrics.increment("isolation-test")
    with patch("common.metrics.monotonic", return_value=16):
        metrics.increment("isolation-test")
        assert metrics.value("isolation-test") == 1


@pytest.mark.django_db
def test_control_outage_fails_readiness_without_exposing_secret():
    with patch.object(caches["default"], "set", side_effect=ConnectionError("private-url")):
        response = APIClient().get("/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["cache"] == "unavailable"
    assert "private-url" not in response.content.decode()


def test_redis_monitor_reports_cache_failure_independently(settings):
    from common.redis_health import redis_samples

    settings.USE_SQLITE = False
    with patch("common.redis_health.Redis.from_url", side_effect=ConnectionError("private-url")):
        families = redis_samples()
    assert families[0][3] == [
        'anicast_redis_up{role="control"} 0',
        'anicast_redis_up{role="ephemeral"} 0',
    ]
    assert "private-url" not in str(families)
