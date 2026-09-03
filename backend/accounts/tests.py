from typing import Any, cast

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import User


def throttle_rate(scope: str, rate: str) -> dict[str, Any]:
    """REST_FRAMEWORK override that changes exactly one throttle scope."""
    framework = cast(dict[str, Any], settings.REST_FRAMEWORK)
    rates = cast(dict[str, str], framework["DEFAULT_THROTTLE_RATES"])
    return {**framework, "DEFAULT_THROTTLE_RATES": {**rates, scope: rate}}


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
@override_settings(REST_FRAMEWORK=throttle_rate("register", "3/hour"))
def test_registration_probing_is_bounded_separately_from_login():
    """Registration answers a question login refuses to, so it needs its own bucket.

    Login is generic on purpose, but registration must tell a returning user their
    address is taken — without email verification there is no other way to say it.
    Sharing login's per-minute budget therefore left an enumeration oracle running
    at roughly 14k probes a day from one address.
    """
    User.objects.create_user(email="known@example.com", password="A-strong-passphrase-2042")

    def probe(email):
        # A fresh client per probe: registering signs the caller in and rotates the
        # CSRF token, and an enumerating script would not reuse a session either.
        # The throttle is keyed on the address, which stays the same.
        return APIClient().post(
            "/api/v1/auth/register/",
            {"email": email, "password": "Another-strong-passphrase-2042"},
            format="json",
            REMOTE_ADDR="203.0.113.42",
        ).status_code

    assert probe("known@example.com") == 400
    assert probe("other-known@example.com") == 201
    assert probe("third@example.com") == 201
    # Budget spent: further probes learn nothing about which addresses exist.
    assert probe("fourth@example.com") == 429
    assert not User.objects.filter(email="fourth@example.com").exists()

    # Login keeps its own, more generous bucket: mistyping a password must not
    # lock someone out because a registration probe ran from the same address.
    assert APIClient().post(
        "/api/v1/auth/login/",
        {"email": "known@example.com", "password": "A-strong-passphrase-2042"},
        format="json",
        REMOTE_ADDR="203.0.113.42",
    ).status_code == 200


@pytest.mark.django_db
def test_csrf_token_is_delivered_in_the_body_not_a_readable_cookie():
    """The token travels in the response body, so the cookie needs no script access.

    `getCsrfToken` in the frontend reads the body; nothing reads
    `document.cookie` for it. Leaving the cookie script-readable therefore only
    handed an injected script the token.
    """
    client = APIClient()
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    assert response.json()["csrfToken"]
    cookie = response.cookies["csrftoken"]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"

    # HttpOnly is a browser-side restriction, so the header flow still works.
    enforcing = APIClient(enforce_csrf_checks=True)
    token = enforcing.get("/api/v1/auth/csrf/").json()["csrfToken"]
    created = enforcing.post(
        "/api/v1/auth/register/",
        {"email": "httponly@example.com", "password": "A-strong-passphrase-2042"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert created.status_code == 201


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
def test_public_profile_settings_are_opt_in_and_csrf_protected():
    user = User.objects.create_user(
        email="social-profile@example.com",
        password="A-strong-passphrase-2042",
        display_name="Social Viewer",
    )
    checked = APIClient(enforce_csrf_checks=True)
    checked.force_login(user)
    payload = {
        "display_name": "Social Viewer",
        "bio": "Люблю научную фантастику и спокойные повседневные истории.",
        "profile_is_public": True,
    }
    assert checked.put("/api/v1/account/profile/", payload, format="json").status_code == 403
    token = checked.get("/api/v1/auth/csrf/").json()["csrfToken"]
    response = checked.put("/api/v1/account/profile/", payload, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200
    assert response.json()["profile_is_public"] is True
    assert response.json()["bio"].startswith("Люблю")
    assert response.json()["public_id"] == str(user.public_id)
    user.refresh_from_db()
    assert user.profile_is_public is True


@pytest.mark.django_db
def test_public_profile_requires_a_display_name():
    user = User.objects.create_user(email="unnamed-profile@example.com", password="A-strong-passphrase-2042")
    client = APIClient()
    client.force_login(user)
    response = client.put(
        "/api/v1/account/profile/",
        {"display_name": "", "bio": "", "profile_is_public": True},
        format="json",
    )
    assert response.status_code == 400
    assert "display_name" in response.json()


@pytest.mark.django_db
def test_account_summary_counts_personal_data():
    from catalog.models import Genre, Title
    from community.models import TitleRating
    from library.models import LibraryEntry, TitleCollection, TitleNote

    user = User.objects.create_user(email="summary@example.com", password="A-strong-passphrase-2042")
    other = User.objects.create_user(email="summary-other@example.com", password="A-strong-passphrase-2042")
    first = Title.objects.create(name="Summary One", slug="900-summary-one")
    second = Title.objects.create(name="Summary Two", slug="901-summary-two")
    action = Genre.objects.create(slug="action", name="Action")
    drama = Genre.objects.create(slug="drama", name="Drama")
    first.genres.set([action, drama])
    second.genres.set([action])
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
    assert body["watched_hours"] == 0
    assert body["average_rating"] == 8.0
    genre_names = [genre["name"] for genre in body["top_genres"]]
    assert "Action" in genre_names
    assert all(genre["share"] > 0 for genre in body["top_genres"])

    anonymous = APIClient()
    assert anonymous.get("/api/v1/account/summary/").status_code in (401, 403)
