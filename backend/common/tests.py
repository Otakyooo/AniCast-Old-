import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_live_health_does_not_require_database():
    response = APIClient().get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.django_db
def test_ready_health_reports_database():
    response = APIClient().get("/health/ready")
    assert response.status_code == 200
    assert response.json()["dependencies"]["database"] == "ok"
