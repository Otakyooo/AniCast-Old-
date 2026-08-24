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


@pytest.mark.django_db
def test_account_summary_counts_personal_data():
    from catalog.models import Title
    from community.models import TitleRating
    from library.models import LibraryEntry, TitleCollection, TitleNote

    user = User.objects.create_user(email="summary@example.com", password="A-strong-passphrase-2042")
    other = User.objects.create_user(email="summary-other@example.com", password="A-strong-passphrase-2042")
    first = Title.objects.create(name="Summary One", slug="900-summary-one")
    second = Title.objects.create(name="Summary Two", slug="901-summary-two")
    LibraryEntry.objects.create(user=user, title=first, status=LibraryEntry.Status.WATCHING, is_favorite=True)
    LibraryEntry.objects.create(user=user, title=second, status=LibraryEntry.Status.PLANNED)
    LibraryEntry.objects.create(user=other, title=first, status=LibraryEntry.Status.COMPLETED)
    TitleNote.objects.create(user=user, title=first, body="context")
    TitleCollection.objects.create(owner=user, name="List", slug="list")
    TitleRating.objects.create(user=user, title=first, value=8)

    client = APIClient()
    client.force_login(user)
    response = client.get("/api/v1/account/summary/")
    assert response.status_code == 200
    body = response.json()
    assert body["library"] == {"planned": 1, "watching": 1, "completed": 0, "on_hold": 0, "dropped": 0}
    assert body["favorites"] == 1
    assert body["notes"] == 1
    assert body["collections"] == 1
    assert body["ratings"] == 1
    assert body["reviews"] == 0

    anonymous = APIClient()
    assert anonymous.get("/api/v1/account/summary/").status_code in (401, 403)
