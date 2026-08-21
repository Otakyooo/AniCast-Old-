import hashlib
import hmac
import time

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import ExternalIdentity, User
from accounts.telegram import TelegramAuthError, verify_telegram_payload


BOT_TOKEN = "123456:test-bot-token"
TEST_CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def signed_payload(**overrides):
    payload = {
        "id": 123456789,
        "first_name": "Иван",
        "last_name": "Петров",
        "username": "viewer",
        "auth_date": int(time.time()),
        **overrides,
    }
    check_string = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    payload["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return payload


def csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    response = client.get("/api/v1/auth/csrf/")
    return client, response.json()["csrfToken"]


def test_telegram_signature_and_freshness():
    payload = signed_payload(auth_date=1_000)
    verified = verify_telegram_payload(payload, BOT_TOKEN, now=1_100)
    assert verified["id"] == 123456789
    payload["first_name"] = "Подмена"
    with pytest.raises(TelegramAuthError):
        verify_telegram_payload(payload, BOT_TOKEN, now=1_100)
    with pytest.raises(TelegramAuthError) as error:
        verify_telegram_payload(signed_payload(auth_date=1_000), BOT_TOKEN, now=1_301)
    assert error.value.code == "telegram_auth_expired"


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN, CACHES=TEST_CACHES)
@pytest.mark.django_db
def test_telegram_login_creates_session_and_reuses_identity():
    cache.clear()
    client, token = csrf_client()
    payload = signed_payload()
    response = client.post("/api/v1/auth/telegram/login/", payload, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 201
    user = User.objects.get()
    assert user.email is None
    assert not user.has_usable_password()
    assert ExternalIdentity.objects.get().subject == "123456789"
    assert client.get("/api/v1/auth/me/").status_code == 200

    client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=client.get("/api/v1/auth/csrf/").json()["csrfToken"])
    cache.clear()
    token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    second = client.post("/api/v1/auth/telegram/login/", signed_payload(username="renamed"), format="json", HTTP_X_CSRFTOKEN=token)
    assert second.status_code == 200
    assert User.objects.count() == 1
    assert ExternalIdentity.objects.get().username == "renamed"


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN, CACHES=TEST_CACHES)
@pytest.mark.django_db
def test_telegram_login_requires_csrf_and_rejects_replay():
    cache.clear()
    payload = signed_payload()
    assert APIClient(enforce_csrf_checks=True).post("/api/v1/auth/telegram/login/", payload, format="json").status_code == 403
    client, token = csrf_client()
    assert client.post("/api/v1/auth/telegram/login/", payload, format="json", HTTP_X_CSRFTOKEN=token).status_code == 201
    client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=client.get("/api/v1/auth/csrf/").json()["csrfToken"])
    token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    replay = client.post("/api/v1/auth/telegram/login/", payload, format="json", HTTP_X_CSRFTOKEN=token)
    assert replay.status_code == 400
    assert replay.json()["code"] == "telegram_auth_replayed"


@pytest.mark.django_db
def test_telegram_login_is_unavailable_without_token():
    client, token = csrf_client()
    response = client.post("/api/v1/auth/telegram/login/", signed_payload(), format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 503
