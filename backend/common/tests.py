import json
import logging
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from common.logging import JsonFormatter


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
