import pytest
from datetime import timedelta

from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Episode, Franchise, Genre, Provider, Source, Title, TitleTranslation
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


def make_playable(episode):
    provider, _ = Provider.objects.get_or_create(
        slug="resume-provider",
        defaults={
            "name": "Resume Provider",
            "is_enabled": True,
            "website_url": "https://watch.example.com",
            "allowed_hosts": ["watch.example.com"],
            "playback_adapter": "external_link",
            "rights_reference": "Resume catalogue entitlement",
            "rights_verified_at": timezone.now(),
        },
    )
    return Source.objects.create(
        episode=episode,
        provider=provider,
        name="Resume Source",
        kind="dub",
        url=f"https://watch.example.com/{episode.title.slug}/{episode.number}",
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
def test_episode_progress_get_is_read_only_and_private(users, titles):
    Episode.objects.create(title=titles[0], number=1, name="Start")
    client = APIClient()
    client.force_login(users[0])

    assert client.get("/api/v1/episodes/first/1/progress/").status_code == 404
    created = client.put(
        "/api/v1/episodes/first/1/progress/",
        {"is_watched": True},
        format="json",
    )
    assert created.status_code == 201
    progress = client.get("/api/v1/episodes/first/1/progress/")
    assert progress.status_code == 200
    assert progress.json()["is_watched"] is True

    other = APIClient()
    other.force_login(users[1])
    assert other.get("/api/v1/episodes/first/1/progress/").status_code == 404


@pytest.mark.django_db
def test_playback_progress_is_monotonic_and_completes_at_ninety_percent(users, titles):
    Episode.objects.create(title=titles[0], number=1, name="Start")
    client = APIClient()
    client.force_login(users[0])

    created = client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 45, "duration_seconds": 100, "event": "progress"},
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["watched_seconds"] == 45
    assert created.json()["duration_seconds"] == 100
    assert created.json()["progress_percent"] == 45
    assert created.json()["is_watched"] is False
    assert "title" not in created.json()
    assert "episode" not in created.json()

    delayed = client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 20, "duration_seconds": 90, "event": "progress"},
        format="json",
    )
    assert delayed.status_code == 200
    assert delayed.json()["watched_seconds"] == 45
    assert delayed.json()["duration_seconds"] == 100
    assert delayed.json()["progress_percent"] == 45

    completed = client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 90, "duration_seconds": 100, "event": "pause"},
        format="json",
    )
    assert completed.status_code == 200
    assert completed.json()["is_watched"] is True
    assert completed.json()["watched_at"] is not None


@pytest.mark.django_db
def test_playback_ended_records_full_duration_and_validates_payload(users, titles):
    Episode.objects.create(title=titles[0], number=1, name="Start")
    client = APIClient()
    client.force_login(users[0])

    ended = client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 12, "duration_seconds": 120, "event": "ended"},
        format="json",
    )
    assert ended.status_code == 201
    assert ended.json()["watched_seconds"] == 120
    assert ended.json()["progress_percent"] == 100
    assert ended.json()["is_watched"] is True

    assert client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 121, "duration_seconds": 120, "event": "progress"},
        format="json",
    ).status_code == 400
    assert client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 12, "duration_seconds": 120, "event": "seek"},
        format="json",
    ).status_code == 400
    assert client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 86_401, "duration_seconds": 86_401, "event": "progress"},
        format="json",
    ).status_code == 400


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
def test_history_entry_delete_removes_only_the_caller_progress_of_one_title(users, titles):
    first = Episode.objects.create(title=titles[0], number=1)
    Episode.objects.create(title=titles[0], number=2)
    other = Episode.objects.create(title=titles[1], number=1)
    client = APIClient()
    client.force_login(users[0])
    client.post("/api/v1/episodes/first/1/progress/")
    client.post("/api/v1/episodes/first/2/progress/")
    EpisodeProgress.objects.create(user=users[0], episode=other, last_opened_at=timezone.now())
    EpisodeProgress.objects.create(user=users[1], episode=first, last_opened_at=timezone.now())

    deleted = client.delete("/api/v1/history/first/")
    assert deleted.status_code == 204
    assert not EpisodeProgress.objects.filter(user=users[0], episode__title=titles[0]).exists()
    # Marks of other titles and of other viewers stay untouched.
    assert EpisodeProgress.objects.filter(user=users[0], episode=other).exists()
    assert EpisodeProgress.objects.filter(user=users[1], episode=first).exists()

    assert client.delete("/api/v1/history/first/").status_code == 404
    assert APIClient().delete("/api/v1/history/first/").status_code in {401, 403}


@pytest.mark.django_db
def test_history_entry_get_returns_watched_marks_of_one_title(users, titles):
    """The player rail reads compact watched marks per title.

    Marks of other titles and other viewers must not leak into the response,
    and an unknown slug answers 404 like the other per-title endpoints.
    """
    first_title_episodes = [
        Episode.objects.create(title=titles[0], number=number) for number in (1, 2, 3)
    ]
    other_title_episode = Episode.objects.create(title=titles[1], number=1)
    EpisodeProgress.objects.create(
        user=users[0], episode=first_title_episodes[0], is_watched=True,
        watched_at=timezone.now(), last_opened_at=timezone.now(),
    )
    EpisodeProgress.objects.create(
        user=users[0], episode=first_title_episodes[2], is_watched=True,
        watched_at=timezone.now(), last_opened_at=timezone.now(),
    )
    # Same viewer, other title: opened but not watched — must not appear.
    EpisodeProgress.objects.create(user=users[0], episode=other_title_episode, last_opened_at=timezone.now())
    # Other viewer, same title: must not leak.
    EpisodeProgress.objects.create(
        user=users[1], episode=first_title_episodes[1], is_watched=True,
        watched_at=timezone.now(), last_opened_at=timezone.now(),
    )

    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/history/first/")
    assert response.status_code == 200
    assert response.json() == {"watched_episode_numbers": [1, 3]}

    assert client.get("/api/v1/history/missing/").status_code == 404
    assert APIClient().get("/api/v1/history/first/").status_code in {401, 403}


@pytest.mark.django_db
def test_continue_watching_requires_auth_and_is_empty_without_progress(users, titles):
    Episode.objects.create(title=titles[0], number=1)
    assert APIClient().get("/api/v1/continue-watching/").status_code in {401, 403}
    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/continue-watching/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_continue_watching_resumes_after_the_watched_episode(users, titles):
    for number in (1, 2, 3):
        make_playable(Episode.objects.create(title=titles[0], number=number))
    make_playable(Episode.objects.create(title=titles[1], number=1))
    client = APIClient()
    client.force_login(users[0])
    client.post("/api/v1/episodes/first/1/progress/")
    client.put("/api/v1/episodes/first/1/progress/", {"is_watched": True}, format="json")
    client.post("/api/v1/episodes/second/1/progress/")

    entries = client.get("/api/v1/continue-watching/").json()
    assert [entry["title"]["slug"] for entry in entries] == ["second", "first"]
    resumed = next(entry for entry in entries if entry["title"]["slug"] == "first")
    assert resumed["last_episode"]["number"] == 1
    assert resumed["is_watched"] is True
    # A watched episode resumes on the next one; an opened-but-unwatched episode
    # resumes on itself, so nothing is skipped.
    assert resumed["resume_episode"]["number"] == 2
    assert resumed["next_episode"]["number"] == 2
    assert resumed["resume_at_seconds"] == 0
    assert resumed["duration_seconds"] is None
    assert resumed["progress_percent"] == 0
    opened = next(entry for entry in entries if entry["title"]["slug"] == "second")
    assert opened["resume_episode"]["number"] == 1
    assert opened["resume_at_seconds"] == 0

    client.put("/api/v1/episodes/first/3/progress/", {"is_watched": True}, format="json")
    assert all(
        entry["title"]["slug"] != "first"
        for entry in client.get("/api/v1/continue-watching/").json()
    )


@pytest.mark.django_db
def test_continue_watching_exposes_resume_time_for_current_episode(users, titles):
    episode = Episode.objects.create(title=titles[0], number=1)
    make_playable(episode)
    client = APIClient()
    client.force_login(users[0])
    client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 48, "duration_seconds": 120, "event": "progress"},
        format="json",
    )

    entry = client.get("/api/v1/continue-watching/").json()[0]

    assert entry["resume_episode"]["number"] == 1
    assert entry["resume_at_seconds"] == 48
    assert entry["duration_seconds"] == 120
    assert entry["progress_percent"] == 40


@pytest.mark.django_db
def test_continue_watching_titles_carry_the_real_episode_total(users, titles):
    """The shelf card shows "episode N of M"; the total must come from the
    payload instead of a guess, and 0 must survive as 0 rather than null."""
    for number in (1, 2, 3):
        make_playable(Episode.objects.create(title=titles[0], number=number))
    Episode.objects.create(title=titles[1], number=1)  # no playable source
    make_playable(Episode.objects.create(title=titles[1], number=2))
    client = APIClient()
    client.force_login(users[0])
    client.post("/api/v1/episodes/first/1/progress/")
    client.post("/api/v1/episodes/second/1/progress/")

    entries = client.get("/api/v1/continue-watching/").json()

    totals = {entry["title"]["slug"]: entry["title"]["episodes_count"] for entry in entries}
    assert totals == {"second": 2, "first": 3}


@pytest.mark.django_db
def test_continue_watching_skips_unplayable_episodes_and_counts_marks(users, titles):
    first = Episode.objects.create(title=titles[0], number=1)
    Episode.objects.create(title=titles[0], number=2)
    playable = Episode.objects.create(title=titles[0], number=3)
    make_playable(playable)
    client = APIClient()
    client.force_login(users[0])
    client.put("/api/v1/episodes/first/1/progress/", {"is_watched": True}, format="json")

    entry = client.get("/api/v1/continue-watching/").json()[0]

    assert first.number == 1
    assert entry["resume_episode"]["number"] == 3
    assert entry["watched_count"] == 1


@pytest.mark.django_db
def test_continue_watching_is_private(users, titles):
    Episode.objects.create(title=titles[0], number=1)
    other = APIClient()
    other.force_login(users[1])
    other.post("/api/v1/episodes/first/1/progress/")
    client = APIClient()
    client.force_login(users[0])
    assert client.get("/api/v1/continue-watching/").json() == []


def _personal_shelf_fixture(user, count, *, with_progress=False):
    """A page-sized shelf of fully populated titles for the budget tests.

    ``translated_value`` calls ``instance.translations.all()`` per localized
    field, and ``TitleSerializer`` also localizes every genre and the franchise.
    Without a prefetch each row costs a handful of queries, so the fixture needs
    real translations and genres for the budget to mean anything.
    """
    franchise = Franchise.objects.create(name="Shelf Franchise", slug="shelf-franchise")
    genres = [Genre.objects.create(name=f"Genre {index}", slug=f"genre-{index}") for index in range(3)]
    for genre in genres:
        genre.translations.create(language="ru", name=f"Жанр {genre.slug}")
    franchise.translations.create(language="ru", name="Франшиза")
    created = []
    for index in range(count):
        title = Title.objects.create(
            name=f"Shelf {index}", slug=f"shelf-{index}", status="ongoing", franchise=franchise
        )
        title.genres.set(genres)
        TitleTranslation.objects.create(title=title, language="ru", name=f"Полка {index}", synopsis="Описание")
        episode = Episode.objects.create(title=title, number=1, name=f"Episode {index}")
        episode.translations.create(language="ru", name=f"Эпизод {index}", synopsis="Серия")
        if with_progress:
            make_playable(episode)
        created.append((title, episode))
    return created


@pytest.mark.django_db
def test_library_list_serializes_a_full_page_within_a_query_budget(users, django_assert_max_num_queries):
    for title, _ in _personal_shelf_fixture(users[0], 20):
        LibraryEntry.objects.create(user=users[0], title=title, status="watching")
    client = APIClient()
    client.force_login(users[0])

    # Session, count, page, then one query per prefetched relation — never per
    # row. The same budget must hold for 1 entry and for a full page of 20.
    with django_assert_max_num_queries(11):
        response = client.get("/api/v1/library/", HTTP_ACCEPT_LANGUAGE="ru")

    assert response.status_code == 200
    assert response.json()["count"] == 20
    first = response.json()["results"][0]["title"]
    assert first["name"].startswith("Полка")
    assert first["franchise"]["name"] == "Франшиза"
    assert all(genre["name"].startswith("Жанр") for genre in first["genres"])


@pytest.mark.django_db
def test_history_list_serializes_a_full_page_within_a_query_budget(users, django_assert_max_num_queries):
    opened_at = timezone.now()
    for index, (_, episode) in enumerate(_personal_shelf_fixture(users[0], 20, with_progress=True)):
        EpisodeProgress.objects.create(
            user=users[0], episode=episode, last_opened_at=opened_at - timedelta(minutes=index)
        )
    client = APIClient()
    client.force_login(users[0])

    # History nests both the title and the episode payloads, so it needs the
    # episode translations on top of the title ones.
    with django_assert_max_num_queries(14):
        response = client.get("/api/v1/history/", HTTP_ACCEPT_LANGUAGE="ru")

    assert response.status_code == 200
    assert response.json()["count"] == 20
    row = response.json()["results"][0]
    assert row["episode"]["name"].startswith("Эпизод")
    assert row["title"]["name"].startswith("Полка")


@pytest.mark.django_db
def test_notes_list_serializes_a_full_page_within_a_query_budget(users, django_assert_max_num_queries):
    for title, _ in _personal_shelf_fixture(users[0], 20):
        TitleNote.objects.create(user=users[0], title=title, body="Заметка")
    client = APIClient()
    client.force_login(users[0])

    with django_assert_max_num_queries(11):
        response = client.get("/api/v1/notes/", HTTP_ACCEPT_LANGUAGE="ru")

    assert response.status_code == 200
    assert response.json()["count"] == 20
    assert response.json()["results"][0]["title"]["name"].startswith("Полка")


@pytest.mark.django_db
def test_continue_watching_cost_follows_the_shelf_cap_not_the_history_size(
    users, django_assert_max_num_queries
):
    """The whole shelf resolves its resume targets in one query.

    The shelf used to stop at twelve titles and pay one source lookup per title.
    Both are gone: every started, unfinished title is returned, and the targets
    are resolved together. The budget is the one the capped shelf already met,
    so returning twice as many entries must not exceed it.
    """
    opened_at = timezone.now()
    for index, (_, episode) in enumerate(_personal_shelf_fixture(users[0], 24, with_progress=True)):
        EpisodeProgress.objects.create(
            user=users[0], episode=episode, last_opened_at=opened_at - timedelta(minutes=index)
        )
    client = APIClient()
    client.force_login(users[0])

    # Constant queries joined the shelf payload: the hidden-titles filter, the
    # completed-titles filter, the franchise siblings (next-part payload) and
    # their localized names — none of them scale with history size.
    with django_assert_max_num_queries(42):
        response = client.get("/api/v1/continue-watching/", HTTP_ACCEPT_LANGUAGE="ru")

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 24
    assert entries[0]["resume_episode"]["name"].startswith("Эпизод")
    assert entries[0]["title"]["name"].startswith("Полка")


@pytest.mark.django_db
def test_continue_watching_drops_a_title_marked_watched_by_hand(users, titles):
    """A manual "Просмотрено" outranks leftover playback progress.

    Deactivation and completion are different claims: the library status is the
    viewer's own statement about the title, so the resume shelf must not keep
    offering an episode of it just because a progress row still exists.
    """
    for number in (1, 2, 3):
        make_playable(Episode.objects.create(title=titles[0], number=number))
    make_playable(Episode.objects.create(title=titles[1], number=1))
    client = APIClient()
    client.force_login(users[0])
    client.post("/api/v1/episodes/first/1/progress/")
    client.post("/api/v1/episodes/second/1/progress/")

    assert {entry["title"]["slug"] for entry in client.get("/api/v1/continue-watching/").json()} == {
        "first",
        "second",
    }

    LibraryEntry.objects.create(user=users[0], title=titles[0], status=LibraryEntry.Status.COMPLETED)

    assert [
        entry["title"]["slug"] for entry in client.get("/api/v1/continue-watching/").json()
    ] == ["second"]

    # The progress row is untouched: marking a title watched is not a delete.
    assert EpisodeProgress.objects.filter(user=users[0], episode__title=titles[0]).exists()


@pytest.mark.django_db
def test_continue_watching_keeps_a_title_that_is_merely_planned_or_on_hold(users, titles):
    """Only "completed" removes a title; other library statuses must not.

    "В планах" and "Отложено" say nothing about finishing, and a viewer who
    parked a title still expects to resume it.
    """
    make_playable(Episode.objects.create(title=titles[0], number=1))
    client = APIClient()
    client.force_login(users[0])
    client.post("/api/v1/episodes/first/1/progress/")

    for status in (LibraryEntry.Status.PLANNED, LibraryEntry.Status.ON_HOLD, LibraryEntry.Status.DROPPED):
        LibraryEntry.objects.update_or_create(user=users[0], title=titles[0], defaults={"status": status})
        assert [
            entry["title"]["slug"] for entry in client.get("/api/v1/continue-watching/").json()
        ] == ["first"], f"{status} must not remove the title from the shelf"


@pytest.mark.django_db
def test_episode_progress_requires_auth_and_csrf(users, titles):
    Episode.objects.create(title=titles[0], number=1)
    assert APIClient().post("/api/v1/episodes/first/1/progress/").status_code in {401, 403}
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(users[0])
    assert client.post("/api/v1/episodes/first/1/progress/").status_code == 403
    assert client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 10, "duration_seconds": 100, "event": "progress"},
        format="json",
    ).status_code == 403


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
def test_recommendations_use_rating_history_and_exclude_engaged_franchises(users, titles):
    from community.models import TitleRating

    franchise = Franchise.objects.create(name="Saga", slug="saga")
    genre = Genre.objects.create(name="Drama", slug="drama")
    titles[0].franchise = franchise
    titles[0].save()
    titles[0].genres.add(genre)
    titles[1].genres.add(genre)
    # A sequel of the franchise the viewer already started: it is their own
    # unfinished story, not a recommendation, and must not appear at all.
    sequel = Title.objects.create(name="Sequel", slug="sequel", year=2026, franchise=franchise)
    sequel.genres.add(genre)
    unrelated = Title.objects.create(name="Unrelated", slug="unrelated-hit")
    unrelated.genres.add(genre)
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
    assert "sequel" not in scores
    # drama weight for an unrelated story: completed entry (1.0) + rating 9 (0.5) + watched (0.5)
    assert scores["unrelated-hit"] == 2.0


@pytest.mark.django_db
def test_recommendations_prefer_franchise_entry_points(users):
    """Within one new franchise the first part is the representative."""
    franchise = Franchise.objects.create(name="New Saga", slug="new-saga")
    genre = Genre.objects.create(name="Drama", slug="drama")
    source = Title.objects.create(name="Source", slug="source")
    source.genres.add(genre)
    LibraryEntry.objects.create(user=users[0], title=source, status="completed")
    first = Title.objects.create(name="First Part", slug="first-part", year=2012, franchise=franchise)
    later = Title.objects.create(name="Later Part", slug="later-part", year=2020, franchise=franchise)
    standalone = Title.objects.create(name="Standalone", slug="standalone")
    for title in (first, later, standalone):
        title.genres.add(genre)
    client = APIClient()
    client.force_login(users[0])
    results = client.get("/api/v1/recommendations/").json()["results"]
    slugs = [item["title"]["slug"] for item in results]
    # The franchise contributes exactly one representative — its entry point.
    # A later season never becomes the recommendation for a story the viewer
    # has not opened.
    assert "first-part" in slugs
    assert "later-part" not in slugs
    assert "standalone" in slugs


@pytest.mark.django_db
def test_recommendations_cap_titles_per_franchise(users):
    """A franchise gets one representative, not a row of its own seasons."""
    genre = Genre.objects.create(name="Drama", slug="drama")
    source = Title.objects.create(name="Source", slug="cap-source")
    source.genres.add(genre)
    LibraryEntry.objects.create(user=users[0], title=source, status="completed")
    # Four seasons of one unengaged franchise plus two standalone titles, all
    # sharing drama.
    franchise = Franchise.objects.create(name="Big Saga", slug="big-saga")
    seasons = [
        Title.objects.create(
            name=f"Season {index}", slug=f"season-{index}", year=2020 + index, franchise=franchise
        )
        for index in range(4)
    ]
    standalones = [
        Title.objects.create(name=f"Other {index}", slug=f"other-{index}", year=2000 + index)
        for index in range(2)
    ]
    for title in [*seasons, *standalones]:
        title.genres.add(genre)
    client = APIClient()
    client.force_login(users[0])
    slugs = [item["title"]["slug"] for item in client.get("/api/v1/recommendations/").json()["results"]]
    franchise_slugs = [slug for slug in slugs if slug.startswith("season-")]
    assert len(franchise_slugs) == 1
    # The franchise representative is the entry point, not a later season.
    assert franchise_slugs == ["season-0"]
    # The standalone candidates are not crowded out by the cap.
    assert set(standalone.slug for standalone in standalones) <= set(slugs)


@pytest.mark.django_db
def test_recommendations_negative_signals_penalize_and_cold_fallback_survives(users, titles):
    from community.models import TitleRating

    hated = Genre.objects.create(name="Horror", slug="horror")
    loved = Genre.objects.create(name="Comedy", slug="comedy")
    pure = Title.objects.create(name="Pure", slug="pure")
    pure.genres.add(loved)
    mixed = Title.objects.create(name="Mixed", slug="mixed")
    mixed.genres.add(loved)
    mixed.genres.add(hated)
    horror_source = Title.objects.create(name="HorrorSource", slug="horror-source")
    horror_source.genres.add(hated)
    comedy_source = Title.objects.create(name="ComedySource", slug="comedy-source")
    comedy_source.genres.add(loved)
    LibraryEntry.objects.create(user=users[0], title=comedy_source, status="planned")
    LibraryEntry.objects.create(user=users[0], title=horror_source, status="dropped")
    TitleRating.objects.create(user=users[0], title=titles[0], value=2)
    titles[0].genres.add(hated)
    client = APIClient()
    client.force_login(users[0])
    results = client.get("/api/v1/recommendations/").json()["results"]
    scores = {item["title"]["slug"]: item["score"] for item in results}
    # planned comedy (+0.5); mixed also absorbs the dropped-horror (-1.0) and low-rating (-0.5) penalties
    assert scores["pure"] == 0.5
    assert scores["mixed"] == -1.0
    slugs = [item["title"]["slug"] for item in results]
    assert slugs.index("pure") < slugs.index("mixed")


@pytest.mark.django_db
def test_recommendations_only_negative_signals_keep_recency_fallback(users, titles):
    horror = Genre.objects.create(name="Horror", slug="horror")
    titles[0].genres.add(horror)
    LibraryEntry.objects.create(user=users[0], title=titles[0], status="dropped")
    old = Title.objects.create(name="Ancient", slug="ancient", year=1999)
    fresh = Title.objects.create(name="Fresh", slug="fresh", year=2026)
    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/recommendations/")
    assert response.status_code == 200
    payload = response.json()
    slugs = [item["title"]["slug"] for item in payload["results"]]
    assert "first" not in slugs
    assert slugs.index(fresh.slug) < slugs.index(old.slug)
    assert all(item["score"] == 0.0 for item in payload["results"])
    assert all(item["reasons"]["genres"] == [] for item in payload["results"])


@pytest.mark.django_db
def test_recommendations_skip_watched_titles_without_library_entry(users):
    """Any watch progress excludes a title from recommendations.

    A partially watched series already sits in Continue Watching; surfacing
    it again as a "recommendation" replays the viewer's own history instead
    of widening the choice.
    """
    drama = Genre.objects.create(name="Drama", slug="drama")
    source = Title.objects.create(name="Source", slug="source")
    source.genres.add(drama)
    LibraryEntry.objects.create(user=users[0], title=source, status="planned")
    finished = Title.objects.create(name="Finished", slug="finished")
    started = Title.objects.create(name="Started", slug="started")
    fresh = Title.objects.create(name="Fresh", slug="fresh")
    for title in (finished, started, fresh):
        title.genres.add(drama)
        Episode.objects.create(title=title, number=1)
        Episode.objects.create(title=title, number=2)
    for number in (1, 2):
        episode = Episode.objects.get(title=finished, number=number)
        EpisodeProgress.objects.create(
            user=users[0], episode=episode, is_watched=True, last_opened_at=timezone.now()
        )
    episode = Episode.objects.get(title=started, number=1)
    EpisodeProgress.objects.create(user=users[0], episode=episode, is_watched=True, last_opened_at=timezone.now())
    client = APIClient()
    client.force_login(users[0])
    slugs = [item["title"]["slug"] for item in client.get("/api/v1/recommendations/").json()["results"]]
    assert "finished" not in slugs
    assert "started" not in slugs
    assert "fresh" in slugs


@pytest.mark.django_db
def test_recommendations_break_score_ties_with_community_rating(users):
    drama = Genre.objects.create(name="Drama", slug="drama")
    source = Title.objects.create(name="Source", slug="source")
    source.genres.add(drama)
    LibraryEntry.objects.create(user=users[0], title=source, status="watching")
    weak = Title.objects.create(name="Weak", slug="weak", year=2026)
    strong = Title.objects.create(name="Strong", slug="strong", year=1990)
    for title in (weak, strong):
        title.genres.add(drama)
    from community.models import TitleRating

    TitleRating.objects.create(user=users[1], title=weak, value=4)
    TitleRating.objects.create(user=users[1], title=strong, value=9)
    client = APIClient()
    client.force_login(users[0])
    slugs = [item["title"]["slug"] for item in client.get("/api/v1/recommendations/").json()["results"]]
    assert slugs.index("strong") < slugs.index("weak")


@pytest.mark.django_db
def test_recommendation_dismissal_hides_until_undone_and_requires_auth_csrf(users, titles):
    from library.models import RecommendationDismissal

    anonymous = APIClient()
    assert anonymous.post("/api/v1/recommendations/first/dismiss/").status_code in {401, 403}
    csrf_client = APIClient(enforce_csrf_checks=True)
    csrf_client.force_login(users[0])
    assert csrf_client.post("/api/v1/recommendations/first/dismiss/").status_code == 403

    drama = Genre.objects.create(name="Drama", slug="drama")
    titles[1].genres.add(drama)
    LibraryEntry.objects.create(user=users[0], title=titles[0], status="watching")
    titles[0].genres.add(drama)

    client = APIClient()
    client.force_login(users[0])
    created = client.post("/api/v1/recommendations/second/dismiss/")
    assert created.status_code == 201
    repeated = client.post("/api/v1/recommendations/second/dismiss/")
    assert repeated.status_code == 200
    assert RecommendationDismissal.objects.filter(user=users[0]).count() == 1

    slugs = [item["title"]["slug"] for item in client.get("/api/v1/recommendations/").json()["results"]]
    assert "second" not in slugs
    assert "second" not in [entry.title.slug for entry in RecommendationDismissal.objects.filter(user=users[1])]

    assert client.delete("/api/v1/recommendations/missing/dismiss/").status_code == 404
    undone = client.delete("/api/v1/recommendations/second/dismiss/")
    assert undone.status_code == 204
    assert client.delete("/api/v1/recommendations/second/dismiss/").status_code == 404
    restored = [
        item["title"]["slug"] for item in client.get("/api/v1/recommendations/").json()["results"]
    ]
    assert "second" in restored
    assert RecommendationDismissal.objects.filter(user=users[0]).count() == 0


@pytest.mark.django_db
def test_recommendations_expose_localized_reasons_with_franchise_flag(users):
    from catalog.models import GenreTranslation

    saga = Franchise.objects.create(name="Saga", slug="saga")
    other = Franchise.objects.create(name="Other", slug="other")
    drama = Genre.objects.create(name="Drama", slug="drama")
    comedy = Genre.objects.create(name="Comedy", slug="comedy")
    thriller = Genre.objects.create(name="Thriller", slug="thriller")
    GenreTranslation.objects.create(genre=drama, language="ru", name="Драма")
    GenreTranslation.objects.create(genre=comedy, language="ru", name="Комедия")
    GenreTranslation.objects.create(genre=thriller, language="ru", name="Триллер")

    source = Title.objects.create(name="Source", slug="source", franchise=saga)
    source.genres.add(drama)
    source.genres.add(comedy)
    LibraryEntry.objects.create(user=users[0], title=source, status="watching")

    # A candidate from a different, unengaged franchise: reasons list only the
    # genres that actually matched; the franchise flag stays false because the
    # viewer's own franchises are excluded from recommendations entirely.
    candidate = Title.objects.create(name="Candidate", slug="candidate", year=2026, franchise=other)
    candidate.genres.add(comedy)
    candidate.genres.add(thriller)

    plain = Title.objects.create(name="Plain", slug="plain")
    plain.genres.add(comedy)

    client = APIClient()
    client.force_login(users[0])
    results = client.get("/api/v1/recommendations/", {"lang": "ru"}).json()["results"]
    by_slug = {item["title"]["slug"]: item["reasons"] for item in results}
    assert by_slug["candidate"] == {"genres": ["Комедия"], "franchise": False}
    assert by_slug["plain"] == {"genres": ["Комедия"], "franchise": False}
    assert "source" not in by_slug


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
        "profile_is_public": False,
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
    assert payload["owner"] == {
        "public_id": str(users[0].public_id),
        "display_name": "Collector",
        "profile_is_public": False,
    }
    assert "email" not in str(payload)
    assert set(payload["items"][0]["title"]) == {
        "name", "slug", "original_name", "synopsis", "title_type", "status", "year", "poster_url", "genres", "franchise",
        "episodes_count", "rating_average", "rating_count", "localized_names",
        "last_episode_number", "next_episode_at", "playable_episodes_count",
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
    assert collection is not None
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


@pytest.mark.django_db
def test_collection_list_is_a_bounded_card_payload(users, django_assert_max_num_queries):
    """The list endpoint renders cards, so it must not carry every nested title.

    At both ceilings (50 collections × 200 items) the old response serialized
    10 000 complete title payloads to draw a few posters per card. The card now
    carries a count and a bounded preview, and the cost must not grow with how
    much the viewer has collected.
    """
    collected = Title.objects.bulk_create(
        [Title(name=f"Collected {index}", slug=f"collected-{index}") for index in range(12)]
    )
    for index, title in enumerate(collected):
        TitleTranslation.objects.create(title=title, language="ru", name=f"Собрано {index}", synopsis="о")
    for list_index in range(6):
        collection = TitleCollection.objects.create(
            owner=users[0], name=f"List {list_index}", slug=f"list-{list_index}"
        )
        TitleCollectionItem.objects.bulk_create(
            [
                TitleCollectionItem(collection=collection, title=title, position=position)
                for position, title in enumerate(collected)
            ]
        )
    client = APIClient()
    client.force_login(users[0])

    # Session read, the annotated collection page, one query for all previews and
    # one for their translations, plus the session write every authenticated
    # request performs. Never a query per collection or per item.
    with django_assert_max_num_queries(8):
        response = client.get("/api/v1/collections/", HTTP_ACCEPT_LANGUAGE="ru")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 6
    card = payload[0]
    assert card["item_count"] == 12
    assert len(card["preview_items"]) == 4
    assert set(card["preview_items"][0]) == {"position", "slug", "name", "poster_url"}
    assert card["preview_items"][0]["name"].startswith("Собрано")
    assert [item["position"] for item in card["preview_items"]] == [0, 1, 2, 3]
    # Cards never carry the nested title payload the detail endpoint returns.
    assert "items" not in card
    assert card["contains_title"] is None


@pytest.mark.django_db
def test_collection_list_answers_membership_for_one_title(users, titles):
    """The title page asks only which collections already contain this title."""
    holding = TitleCollection.objects.create(owner=users[0], name="Holding", slug="holding")
    TitleCollectionItem.objects.create(collection=holding, title=titles[0], position=0)
    TitleCollection.objects.create(owner=users[0], name="Empty", slug="empty-list")
    client = APIClient()
    client.force_login(users[0])

    payload = client.get(f"/api/v1/collections/?title={titles[0].slug}").json()
    membership = {card["slug"]: card["contains_title"] for card in payload}
    assert membership == {"holding": True, "empty-list": False}

    # Another account's collection never leaks into the answer.
    other = TitleCollection.objects.create(owner=users[1], name="Other", slug="other-list")
    TitleCollectionItem.objects.create(collection=other, title=titles[0], position=0)
    payload = client.get(f"/api/v1/collections/?title={titles[0].slug}").json()
    assert {card["slug"] for card in payload} == {"holding", "empty-list"}
    assert client.get("/api/v1/collections/?title=does-not-exist").json()[0]["contains_title"] is False


@pytest.mark.django_db
def test_collection_insert_rewrites_positions_in_a_bounded_number_of_queries(
    users, titles, django_assert_max_num_queries
):
    """Adding one title must not cost a query per existing item.

    ``unique_collection_position`` forces a full rewrite of the order, but that
    rewrite is two statements. The old implementation saved every row twice,
    which at the 200-item ceiling meant roughly 405 queries under row locks to
    add a single title.
    """
    collection = TitleCollection.objects.create(owner=users[0], name="Favorites", slug="favorites")
    existing = Title.objects.bulk_create(
        [Title(name=f"Existing {index}", slug=f"existing-{index}") for index in range(40)]
    )
    TitleCollectionItem.objects.bulk_create(
        [
            TitleCollectionItem(collection=collection, title=title, position=position)
            for position, title in enumerate(existing)
        ]
    )
    client = APIClient()
    client.force_login(users[0])

    with django_assert_max_num_queries(18):
        response = client.post(
            "/api/v1/collections/favorites/items/",
            {"title_slug": titles[0].slug, "position": 5},
            format="json",
        )

    assert response.status_code == 201
    assert response.json()["position"] == 5
    positions = list(
        TitleCollectionItem.objects.filter(collection=collection)
        .order_by("position")
        .values_list("position", "title__slug")
    )
    assert [position for position, _ in positions] == list(range(41))
    assert positions[5][1] == titles[0].slug
    assert positions[4][1] == "existing-4"
    assert positions[6][1] == "existing-5"


@pytest.mark.django_db
def test_progress_records_voice_selection_and_continue_restores_it(users, titles):
    """The played voice variant rides along with progress and the shelf."""
    episode = Episode.objects.create(title=titles[0], number=1)
    make_playable(episode)
    client = APIClient()
    client.force_login(users[0])
    response = client.post(
        "/api/v1/episodes/first/1/progress/",
        {"source_selection_key": "abc123", "source_name": "AniLibria", "source_kind": "dub"},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["source_name"] == "AniLibria"
    entry = client.get("/api/v1/continue-watching/").json()[0]
    assert entry["source_selection_key"] == "abc123"
    assert entry["source_name"] == "AniLibria"
    assert entry["source_kind"] == "dub"
    # A later heartbeat without voice data keeps the stored snapshot.
    client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 30, "duration_seconds": 600, "event": "pause"},
        format="json",
    )
    entry = client.get("/api/v1/continue-watching/").json()[0]
    assert entry["source_selection_key"] == "abc123"
    # A heartbeat with a different voice replaces the snapshot.
    client.patch(
        "/api/v1/episodes/first/1/progress/",
        {"watched_seconds": 60, "duration_seconds": 600, "event": "pause",
         "source_selection_key": "def456", "source_name": "Studio Band", "source_kind": "dub"},
        format="json",
    )
    entry = client.get("/api/v1/continue-watching/").json()[0]
    assert entry["source_selection_key"] == "def456"
    assert entry["source_name"] == "Studio Band"


@pytest.mark.django_db
def test_continue_watching_hide_keeps_history_and_is_reversible(users, titles):
    episode = Episode.objects.create(title=titles[0], number=1)
    make_playable(episode)
    client = APIClient()
    client.force_login(users[0])
    client.post("/api/v1/episodes/first/1/progress/")
    assert len(client.get("/api/v1/continue-watching/").json()) == 1

    assert client.post("/api/v1/continue-watching/first/hide/").status_code == 201
    assert client.get("/api/v1/continue-watching/").json() == []
    # Hiding removed the card, not the history: the progress row survives.
    assert client.get("/api/v1/history/first/").json()["watched_episode_numbers"] == []
    progress = client.get("/api/v1/episodes/first/1/progress/")
    assert progress.status_code == 200
    # Repeat-hide is idempotent, unhide restores the card.
    assert client.post("/api/v1/continue-watching/first/hide/").status_code == 200
    assert client.delete("/api/v1/continue-watching/first/hide/").status_code == 204
    assert len(client.get("/api/v1/continue-watching/").json()) == 1
    assert client.delete("/api/v1/continue-watching/first/hide/").status_code == 404


@pytest.mark.django_db
def test_library_statuses_returns_compact_map(users, titles):
    LibraryEntry.objects.create(user=users[0], title=titles[0], status="watching")
    LibraryEntry.objects.create(
        user=users[0], title=titles[1], status="planned", is_favorite=True
    )
    LibraryEntry.objects.create(user=users[1], title=titles[0], status="completed")
    client = APIClient()
    client.force_login(users[0])
    response = client.get("/api/v1/library/statuses/")
    assert response.status_code == 200
    entries = {row["slug"]: row for row in response.json()["entries"]}
    assert set(entries) == {"first", "second"}
    assert entries["first"] == {"slug": "first", "status": "watching", "is_favorite": False}
    assert entries["second"]["is_favorite"] is True
    assert APIClient().get("/api/v1/library/statuses/").status_code in {401, 403}


@pytest.mark.django_db
def test_auto_add_to_watching_files_first_playback(users, titles):
    episode = Episode.objects.create(title=titles[0], number=1)
    make_playable(episode)
    users[0].auto_add_to_watching = True
    users[0].save(update_fields=["auto_add_to_watching"])
    client = APIClient()
    client.force_login(users[0])
    assert client.post("/api/v1/episodes/first/1/progress/").status_code == 201
    entry = LibraryEntry.objects.get(user=users[0], title=titles[0])
    assert entry.status == LibraryEntry.Status.WATCHING
    # An explicit status is never overwritten by later playbacks.
    entry.status = LibraryEntry.Status.COMPLETED
    entry.save(update_fields=["status"])
    client.post("/api/v1/episodes/first/1/progress/")
    entry.refresh_from_db()
    assert entry.status == LibraryEntry.Status.COMPLETED
    # Off by default: the second user gets no surprise library entry.
    users[1].auto_add_to_watching = False
    users[1].save(update_fields=["auto_add_to_watching"])
    other = APIClient()
    other.force_login(users[1])
    other.post("/api/v1/episodes/first/1/progress/")
    assert not LibraryEntry.objects.filter(user=users[1]).exists()


@pytest.mark.django_db
def test_continue_watching_reports_franchise_next_part(users, titles):
    franchise = Franchise.objects.create(name="Story", slug="story")
    first = Title.objects.create(name="Part One", slug="part-one", year=2018, franchise=franchise)
    second = Title.objects.create(name="Part Two", slug="part-two", year=2022, franchise=franchise)
    episode = Episode.objects.create(title=first, number=1)
    make_playable(episode)
    Episode.objects.create(title=second, number=1)
    client = APIClient()
    client.force_login(users[0])
    client.post("/api/v1/episodes/part-one/1/progress/")
    entries = client.get("/api/v1/continue-watching/", {"lang": "ru"}).json()
    assert entries[0]["franchise_next"]["slug"] == "part-two"
    assert entries[0]["franchise_next"]["year"] == 2022
    # Titles without a franchise report no next part.
    solo = Episode.objects.create(title=titles[0], number=1)
    make_playable(solo)
    client.post("/api/v1/episodes/first/1/progress/")
    entries = {entry["title"]["slug"]: entry for entry in client.get("/api/v1/continue-watching/").json()}
    assert entries["first"]["franchise_next"] is None
