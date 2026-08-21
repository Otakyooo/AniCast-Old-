from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import ExternalIdentity, TelegramLoginChallenge, User


TELEGRAM_SETTINGS = {
    "TELEGRAM_BOT_TOKEN": "123456:test-bot-token",
    "TELEGRAM_BOT_USERNAME": "anicast_test_bot",
    "TELEGRAM_WEBHOOK_SECRET": "test-webhook-secret",
}


def csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    response = client.get("/api/v1/auth/csrf/")
    return client, response.json()["csrfToken"]


def create_challenge(client, csrf):
    response = client.post("/api/v1/auth/telegram/challenge/", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 201
    return response.json()["token"]


def approve(token, secret="test-webhook-secret", telegram_id=123456789):
    return APIClient(enforce_csrf_checks=True).post(
        "/api/v1/auth/telegram/webhook/",
        {
            "update_id": 1,
            "message": {
                "text": f"/start {token}",
                "from": {"id": telegram_id, "first_name": "Иван", "last_name": "Петров", "username": "viewer"},
                "chat": {"id": telegram_id},
            },
        },
        format="json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret,
    )


@override_settings(**TELEGRAM_SETTINGS)
@pytest.mark.django_db
def test_bot_confirmation_creates_session_and_consumes_challenge():
    client, csrf = csrf_client()
    token = create_challenge(client, csrf)
    pending = client.post(
        "/api/v1/auth/telegram/challenge/complete/",
        {"token": token},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert pending.status_code == 202

    webhook = approve(token)
    assert webhook.status_code == 200
    assert webhook.json()["method"] == "sendMessage"
    completed = client.post(
        "/api/v1/auth/telegram/challenge/complete/",
        {"token": token},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert completed.status_code == 200
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert User.objects.count() == 1
    assert ExternalIdentity.objects.get().subject == "123456789"
    assert TelegramLoginChallenge.objects.get().status == TelegramLoginChallenge.Status.CONSUMED


@override_settings(**TELEGRAM_SETTINGS)
@pytest.mark.django_db
def test_challenge_is_bound_to_browser_session():
    owner, csrf = csrf_client()
    token = create_challenge(owner, csrf)
    approve(token)
    attacker, attacker_csrf = csrf_client()
    response = attacker.post(
        "/api/v1/auth/telegram/challenge/complete/",
        {"token": token},
        format="json",
        HTTP_X_CSRFTOKEN=attacker_csrf,
    )
    assert response.status_code == 404
    assert attacker.get("/api/v1/auth/me/").status_code in {401, 403}


@override_settings(**TELEGRAM_SETTINGS)
@pytest.mark.django_db
def test_expired_and_replayed_challenges_are_rejected():
    client, csrf = csrf_client()
    token = create_challenge(client, csrf)
    TelegramLoginChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    expired = client.post(
        "/api/v1/auth/telegram/challenge/complete/",
        {"token": token},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert expired.status_code == 410
    assert approve(token).status_code == 200
    assert User.objects.count() == 0


@override_settings(**TELEGRAM_SETTINGS)
@pytest.mark.django_db
def test_webhook_requires_secret_and_challenge_requires_csrf():
    client = APIClient(enforce_csrf_checks=True)
    assert client.post("/api/v1/auth/telegram/challenge/").status_code == 403
    owner, csrf = csrf_client()
    token = create_challenge(owner, csrf)
    assert approve(token, secret="wrong-secret").status_code == 403
    assert TelegramLoginChallenge.objects.get().status == TelegramLoginChallenge.Status.PENDING


@pytest.mark.django_db
def test_challenge_is_unavailable_without_configuration():
    client, csrf = csrf_client()
    response = client.post("/api/v1/auth/telegram/challenge/", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 503
