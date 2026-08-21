import pytest
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Episode, Genre, Title
from library.models import EpisodeProgress, LibraryEntry, TitleNote


@pytest.fixture
def users(db):
    return (
        User.objects.create_user(email="one@example.com", password="A-strong-passphrase-2042"),
        User.objects.create_user(email="two@example.com", password="A-strong-passphrase-2042"),
    )


@pytest.fixture
def titles(db):
    return (
        Title.objects.create(name="First", slug="first", status="ongoing"),
        Title.objects.create(name="Second", slug="second", status="finished"),
    )


@pytest.mark.django_db
def test_library_requires_authentication(titles):
    client = APIClient()
    assert client.get("/api/v1/library/").status_code in {401, 403}
    assert client.put("/api/v1/library/first/", {"status": "planned"}, format="json").status_code in {401, 403}


@pytest.mark.django_db
def test_put_creates_and_updates_single_entry(users, titles):
    client = APIClient()
    client.force_login(users[0])
    created = client.put(
        "/api/v1/library/first/",
        {"status": "planned", "is_favorite": False},
        format="json",
    )
    assert created.status_code == 201
    updated = client.put(
        "/api/v1/library/first/",
        {"status": "watching", "is_favorite": True},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "watching"
    assert updated.json()["is_favorite"] is True
    assert LibraryEntry.objects.count() == 1


@pytest.mark.django_db
def test_library_is_private_and_filters_combine(users, titles):
    LibraryEntry.objects.create(user=users[0], title=titles[0], status="watching", is_favorite=True)
    LibraryEntry.objects.create(user=users[0], title=titles[1], status="completed")
    LibraryEntry.objects.create(user=users[1], title=titles[1], status="watching", is_favorite=True)
    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/library/?status=watching&favorite=true")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["title"]["slug"] == "first"
    assert client.get("/api/v1/library/?status=unknown").status_code == 400
    assert client.get("/api/v1/library/?favorite=perhaps").status_code == 400


@pytest.mark.django_db
def test_library_detail_and_delete_are_scoped_to_user(users, titles):
    LibraryEntry.objects.create(user=users[0], title=titles[0])
    client = APIClient()
    client.force_login(users[1])
    assert client.get("/api/v1/library/first/").status_code == 404
    client.force_login(users[0])
    assert client.get("/api/v1/library/first/").status_code == 200
    assert client.delete("/api/v1/library/first/").status_code == 204
    assert not LibraryEntry.objects.exists()


@pytest.mark.django_db
def test_library_mutation_requires_csrf(users, titles):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(users[0])
    response = client.put("/api/v1/library/first/", {"status": "planned"}, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_open_episode_creates_truthful_history_and_preserves_watched_state(users, titles):
    episode = Episode.objects.create(title=titles[0], number=1, name="Start")
    client = APIClient()
    client.force_login(users[0])
    opened = client.post("/api/v1/episodes/first/1/progress/")
    assert opened.status_code == 201
    assert opened.json()["is_watched"] is False
    assert opened.json()["episode"]["id"] == episode.id

    watched = client.put("/api/v1/episodes/first/1/progress/", {"is_watched": True}, format="json")
    assert watched.status_code == 200
    assert watched.json()["watched_at"] is not None
    reopened = client.post("/api/v1/episodes/first/1/progress/")
    assert reopened.status_code == 200
    assert reopened.json()["is_watched"] is True


@pytest.mark.django_db
def test_history_is_private_and_ordered_by_last_open(users, titles):
    first = Episode.objects.create(title=titles[0], number=1)
    second = Episode.objects.create(title=titles[1], number=1)
    client = APIClient()
    client.force_login(users[0])
    client.post("/api/v1/episodes/first/1/progress/")
    client.post("/api/v1/episodes/second/1/progress/")
    EpisodeProgress.objects.create(user=users[1], episode=first, last_opened_at="2026-01-01T00:00:00Z")
    response = client.get("/api/v1/history/")
    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert response.json()["results"][0]["episode"]["id"] == second.id


@pytest.mark.django_db
def test_episode_progress_requires_auth_and_csrf(users, titles):
    Episode.objects.create(title=titles[0], number=1)
    assert APIClient().post("/api/v1/episodes/first/1/progress/").status_code in {401, 403}
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(users[0])
    assert client.post("/api/v1/episodes/first/1/progress/").status_code == 403


@pytest.mark.django_db
def test_title_note_upsert_list_and_delete_are_private(users, titles):
    client = APIClient()
    assert client.get("/api/v1/notes/").status_code in {401, 403}
    client.force_login(users[0])
    created = client.put("/api/v1/notes/first/", {"body": "Remember this detail"}, format="json")
    assert created.status_code == 201
    updated = client.put("/api/v1/notes/first/", {"body": "Updated detail"}, format="json")
    assert updated.status_code == 200
    assert TitleNote.objects.filter(user=users[0], title=titles[0]).count() == 1
    TitleNote.objects.create(user=users[1], title=titles[1], body="Private")
    listing = client.get("/api/v1/notes/")
    assert listing.status_code == 200
    assert listing.json()["count"] == 1
    assert client.get("/api/v1/notes/second/").status_code == 404
    assert client.delete("/api/v1/notes/first/").status_code == 204


@pytest.mark.django_db
def test_title_note_rejects_empty_body_and_requires_csrf(users, titles):
    client = APIClient()
    client.force_login(users[0])
    assert client.put("/api/v1/notes/first/", {"body": "   "}, format="json").status_code == 400
    checked = APIClient(enforce_csrf_checks=True)
    checked.force_login(users[0])
    assert checked.put("/api/v1/notes/first/", {"body": "Blocked"}, format="json").status_code == 403


@pytest.mark.django_db
def test_recommendations_exclude_library_and_rank_shared_genres(users, titles):
    genre = Genre.objects.create(name="Drama", slug="drama")
    titles[0].genres.add(genre)
    titles[1].genres.add(genre)
    third = Title.objects.create(name="Third", slug="third")
    LibraryEntry.objects.create(user=users[0], title=titles[0], status="watching")
    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/recommendations/")
    assert response.status_code == 200
    slugs = [item["title"]["slug"] for item in response.json()["results"]]
    assert titles[0].slug not in slugs
    assert slugs[0] == titles[1].slug
    assert response.json()["results"][0]["score"] == 1
    assert third.slug in slugs
    assert APIClient().get("/api/v1/recommendations/").status_code in {401, 403}
