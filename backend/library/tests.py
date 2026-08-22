import pytest
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Episode, Franchise, Genre, Title, TitleTranslation
from django.utils import timezone

from library.models import EpisodeProgress, LibraryEntry, TitleCollection, TitleCollectionItem, TitleNote


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
    assert response.json()["results"][0]["score"] == 1.0
    assert third.slug not in slugs
    assert APIClient().get("/api/v1/recommendations/").status_code in {401, 403}


@pytest.mark.django_db
def test_recommendations_ignore_dropped_genres_and_weight_signals(users, titles):
    dropped_genre = Genre.objects.create(name="Horror", slug="horror")
    loved_genre = Genre.objects.create(name="Comedy", slug="comedy")
    related = Title.objects.create(name="Related", slug="related")
    related.genres.add(loved_genre)
    horror_only = Title.objects.create(name="Scary", slug="scary")
    horror_only.genres.add(dropped_genre)
    source = Title.objects.create(name="Source", slug="source")
    source.genres.add(loved_genre)
    titles[0].genres.add(dropped_genre)
    LibraryEntry.objects.create(user=users[0], title=titles[0], status="dropped")
    LibraryEntry.objects.create(user=users[0], title=source, status="planned")
    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/recommendations/")
    assert response.status_code == 200
    slugs = [item["title"]["slug"] for item in response.json()["results"]]
    assert related.slug in slugs
    assert "scary" not in slugs
    assert titles[1].slug not in slugs
    scores = {item["title"]["slug"]: item["score"] for item in response.json()["results"]}
    assert scores[related.slug] == 0.5


@pytest.mark.django_db
def test_recommendations_use_ratings_history_and_franchise_boost(users, titles):
    from community.models import TitleRating

    franchise = Franchise.objects.create(name="Saga", slug="saga")
    genre = Genre.objects.create(name="Drama", slug="drama")
    titles[0].franchise = franchise
    titles[0].save()
    titles[0].genres.add(genre)
    titles[1].genres.add(genre)
    sequel = Title.objects.create(name="Sequel", slug="sequel", year=2026)
    sequel.franchise = franchise
    sequel.save()
    sequel.genres.add(genre)
    LibraryEntry.objects.create(user=users[0], title=titles[0], status="completed")
    TitleRating.objects.create(user=users[0], title=titles[1], value=9)
    episode = Episode.objects.create(title=titles[1], number=1)
    EpisodeProgress.objects.create(user=users[0], episode=episode, is_watched=True, last_opened_at=timezone.now())
    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/recommendations/")
    assert response.status_code == 200
    results = response.json()["results"]
    scores = {item["title"]["slug"]: item["score"] for item in results}
    # drama weight: completed library entry (1.0) + rating 9 (0.5) + watched history (0.5)
    assert scores["sequel"] == 2.0 + 3.0
    assert results[0]["title"]["slug"] == "sequel"


@pytest.mark.django_db
def test_recommendations_cold_start_orders_by_recency(users, titles):
    old = Title.objects.create(name="Ancient", slug="ancient", year=1999)
    fresh = Title.objects.create(name="Fresh", slug="fresh", year=2026)
    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/recommendations/")
    assert response.status_code == 200
    slugs = [item["title"]["slug"] for item in response.json()["results"]]
    assert slugs.index(fresh.slug) < slugs.index(old.slug)
    assert all(item["score"] == 0.0 for item in response.json()["results"])



def create_collection(client, **overrides):
    payload = {"name": "Favorites", "slug": "favorites", "description": "Selected titles"}
    payload.update(overrides)
    return client.post("/api/v1/collections/", payload, format="json")


@pytest.mark.django_db
def test_collection_crud_is_authenticated_and_owner_scoped(users):
    anonymous = APIClient()
    assert anonymous.get("/api/v1/collections/").status_code in {401, 403}
    assert create_collection(anonymous).status_code in {401, 403}

    owner = APIClient()
    owner.force_login(users[0])
    created = create_collection(owner)
    assert created.status_code == 201
    assert created.json()["slug"] == "favorites"
    assert created.json()["owner"] == {
        "public_id": str(users[0].public_id),
        "display_name": users[0].display_name,
    }
    assert "email" not in created.json()["owner"]
    updated = owner.patch(
        "/api/v1/collections/favorites/", {"name": "Best", "is_public": True}, format="json"
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Best"

    other = APIClient()
    other.force_login(users[1])
    assert other.get("/api/v1/collections/favorites/").status_code == 404
    assert other.patch("/api/v1/collections/favorites/", {"name": "Stolen"}, format="json").status_code == 404
    assert other.delete("/api/v1/collections/favorites/").status_code == 404
    assert owner.delete("/api/v1/collections/favorites/").status_code == 204


@pytest.mark.django_db
def test_collection_mutations_require_csrf(users):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(users[0])
    assert create_collection(client).status_code == 403
    collection = TitleCollection.objects.create(owner=users[0], name="Favorites", slug="favorites")
    assert client.patch(f"/api/v1/collections/{collection.slug}/", {"name": "Blocked"}, format="json").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("slug", ["new", "edit", "public", "api", "Upper", "two_words", "кириллица", "-bad", "bad-"])
def test_collection_slug_rules(users, slug):
    client = APIClient()
    client.force_login(users[0])
    assert create_collection(client, slug=slug).status_code == 400


@pytest.mark.django_db
def test_collection_slug_is_unique_per_owner_and_immutable(users):
    first = APIClient()
    first.force_login(users[0])
    assert create_collection(first).status_code == 201
    assert create_collection(first).status_code == 400
    assert first.patch("/api/v1/collections/favorites/", {"slug": "renamed"}, format="json").status_code == 400
    second = APIClient()
    second.force_login(users[1])
    assert create_collection(second).status_code == 201


@pytest.mark.django_db
def test_public_collection_visibility_cache_and_payload_safety(users, titles):
    users[0].display_name = "Collector"
    users[0].save(update_fields=["display_name"])
    private = TitleCollection.objects.create(owner=users[0], name="Private", slug="private")
    public = TitleCollection.objects.create(owner=users[0], name="Public", slug="public-list", is_public=True)
    TitleCollectionItem.objects.create(collection=public, title=titles[0], position=0)
    client = APIClient()
    base = f"/api/v1/public/collections/{users[0].public_id}"
    assert client.get(f"{base}/{private.slug}/").status_code == 404
    response = client.get(f"{base}/{public.slug}/")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    payload = response.json()
    assert payload["owner"] == {"public_id": str(users[0].public_id), "display_name": "Collector"}
    assert "email" not in str(payload)
    assert set(payload["items"][0]["title"]) == {
        "name", "slug", "original_name", "synopsis", "title_type", "status", "year", "poster_url", "genres", "franchise"
    }
    assert not {"episodes", "sources", "playback", "user", "id"} & set(payload["items"][0]["title"])


@pytest.mark.django_db
def test_collection_items_add_move_delete_are_dense_and_reject_duplicates(users, titles):
    third = Title.objects.create(name="Third", slug="third")
    client = APIClient()
    client.force_login(users[0])
    assert create_collection(client).status_code == 201
    assert client.post("/api/v1/collections/favorites/items/", {"title_slug": "first"}, format="json").status_code == 201
    assert client.post("/api/v1/collections/favorites/items/", {"title_slug": "second"}, format="json").status_code == 201
    inserted = client.post(
        "/api/v1/collections/favorites/items/", {"title_slug": third.slug, "position": 1}, format="json"
    )
    assert inserted.status_code == 201
    assert client.post("/api/v1/collections/favorites/items/", {"title_slug": "first"}, format="json").status_code == 400
    moved = client.patch("/api/v1/collections/favorites/items/second/", {"position": 0}, format="json")
    assert moved.status_code == 200
    assert client.delete("/api/v1/collections/favorites/items/third/").status_code == 204
    detail = client.get("/api/v1/collections/favorites/").json()
    assert [(item["title"]["slug"], item["position"]) for item in detail["items"]] == [
        ("second", 0), ("first", 1)
    ]


@pytest.mark.django_db
def test_collection_limits(users, titles):
    client = APIClient()
    client.force_login(users[0])
    TitleCollection.objects.bulk_create(
        [TitleCollection(owner=users[0], name=f"List {index}", slug=f"list-{index}") for index in range(50)]
    )
    assert create_collection(client).status_code == 400
    collection = TitleCollection.objects.filter(owner=users[0]).first()
    extra_titles = Title.objects.bulk_create(
        [Title(name=f"Limit {index}", slug=f"limit-{index}") for index in range(200)]
    )
    TitleCollectionItem.objects.bulk_create(
        [TitleCollectionItem(collection=collection, title=title, position=index) for index, title in enumerate(extra_titles)]
    )
    assert client.post(
        f"/api/v1/collections/{collection.slug}/items/", {"title_slug": titles[0].slug}, format="json"
    ).status_code == 400


@pytest.mark.django_db
def test_collection_title_serialization_honors_requested_language(users, titles):
    TitleTranslation.objects.create(title=titles[0], language="ru", name="Первый", synopsis="Описание")
    collection = TitleCollection.objects.create(owner=users[0], name="Public", slug="localized", is_public=True)
    TitleCollectionItem.objects.create(collection=collection, title=titles[0], position=0)
    url = f"/api/v1/public/collections/{users[0].public_id}/{collection.slug}/"
    assert APIClient().get(url, HTTP_ACCEPT_LANGUAGE="ru").json()["items"][0]["title"]["name"] == "Первый"
    assert APIClient().get(url, HTTP_ACCEPT_LANGUAGE="en").json()["items"][0]["title"]["name"] == "First"
