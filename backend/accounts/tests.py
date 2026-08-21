import pytest
from rest_framework.test import APIClient

from accounts.models import User


def csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    return client, response.json()["csrfToken"]


@pytest.mark.django_db
def test_registration_creates_authenticated_session():
    client, token = csrf_client()
    response = client.post(
        "/api/v1/auth/register/",
        {"email": "Viewer@Example.com", "display_name": "Viewer", "password": "A-strong-passphrase-2042"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 201
    assert response.json()["email"] == "viewer@example.com"
    assert "password" not in response.json()
    assert User.objects.get().display_name == "Viewer"
    assert client.get("/api/v1/auth/me/").status_code == 200


@pytest.mark.django_db
def test_auth_mutations_require_csrf():
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        "/api/v1/auth/register/",
        {"email": "viewer@example.com", "password": "A-strong-passphrase-2042"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_duplicate_email_is_rejected_case_insensitively():
    User.objects.create_user(email="viewer@example.com", password="A-strong-passphrase-2042")
    client, token = csrf_client()
    response = client.post(
        "/api/v1/auth/register/",
        {"email": "VIEWER@example.com", "password": "Another-strong-passphrase-2042"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 400
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_login_and_logout_session_flow():
    User.objects.create_user(email="viewer@example.com", password="A-strong-passphrase-2042")
    client, token = csrf_client()
    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": "viewer@example.com", "password": "A-strong-passphrase-2042"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert login_response.status_code == 200
    assert client.get("/api/v1/auth/me/").json()["email"] == "viewer@example.com"

    refreshed_token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    logout_response = client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=refreshed_token)
    assert logout_response.status_code == 204
    assert client.get("/api/v1/auth/me/").status_code in {401, 403}


@pytest.mark.django_db
def test_login_does_not_reveal_which_credential_failed():
    User.objects.create_user(email="viewer@example.com", password="A-strong-passphrase-2042")
    client, token = csrf_client()
    response = client.post(
        "/api/v1/auth/login/",
        {"email": "viewer@example.com", "password": "incorrect-password"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 400
    assert "Неверный email или пароль" in str(response.json())


@pytest.mark.django_db
def test_user_can_update_preferred_language():
    user = User.objects.create_user(email="language@example.com", password="A-strong-passphrase-2042")
    client = APIClient()
    client.force_login(user)
    response = client.put("/api/v1/auth/preferences/", {"preferred_language": "en"}, format="json")
    assert response.status_code == 200
    assert response.json()["preferred_language"] == "en"
    user.refresh_from_db()
    assert user.preferred_language == "en"
    assert client.put("/api/v1/auth/preferences/", {"preferred_language": "xx"}, format="json").status_code == 400


@pytest.mark.django_db
def test_user_public_ids_are_stable_unique_uuids():
    first = User.objects.create_user(email="public-one@example.com")
    second = User.objects.create_user(email="public-two@example.com")
    public_id = first.public_id
    first.save()
    first.refresh_from_db()
    assert first.public_id == public_id
    assert first.public_id != second.public_id
