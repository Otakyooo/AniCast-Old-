import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Title
from community.models import ProfileFollow, TitleReview
from library.models import TitleCollection, TitleCollectionItem


@pytest.fixture
def community_data(db):
    first = User.objects.create_user(email="first-community@example.com", password="A-strong-passphrase-2042", display_name="First")
    second = User.objects.create_user(email="second-community@example.com", password="A-strong-passphrase-2042", display_name="Second")
    title = Title.objects.create(name="Community Title", slug="community-title")
    return first, second, title


@pytest.mark.django_db
def test_community_summary_is_private_no_store(community_data):
    """The summary mixes public aggregates with the viewer's own state."""
    _, _, title = community_data
    response = APIClient().get(f"/api/v1/titles/{title.slug}/community/")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, private"


@pytest.mark.django_db
def test_ratings_are_private_to_writer_and_publicly_aggregated(community_data):
    first, second, title = community_data
    first_client = APIClient()
    first_client.force_login(first)
    assert first_client.put(f"/api/v1/community/ratings/{title.slug}/", {"value": 9}, format="json").status_code == 201
    second_client = APIClient()
    second_client.force_login(second)
    assert second_client.put(f"/api/v1/community/ratings/{title.slug}/", {"value": 7}, format="json").status_code == 201
    summary = APIClient().get(f"/api/v1/titles/{title.slug}/community/").json()
    assert summary["average_rating"] == 8.0
    assert summary["rating_count"] == 2
    assert summary["my_rating"] is None
    own = first_client.get(f"/api/v1/titles/{title.slug}/community/").json()
    assert own["my_rating"]["value"] == 9
    assert first_client.put(f"/api/v1/community/ratings/{title.slug}/", {"value": 11}, format="json").status_code == 400


@pytest.mark.django_db
def test_reviews_stay_private_until_approved_and_edits_reset_status(community_data):
    first, _, title = community_data
    client = APIClient()
    client.force_login(first)
    created = client.put(
        f"/api/v1/community/reviews/{title.slug}/",
        {"body": "A thoughtful review with enough detail.", "contains_spoilers": True},
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert APIClient().get("/api/v1/community/reviews/").json()["count"] == 0
    review = TitleReview.objects.get()
    review.status = TitleReview.Status.APPROVED
    review.published_at = timezone.now()
    review.save(update_fields=["status", "published_at"])
    assert APIClient().get("/api/v1/community/reviews/").json()["count"] == 1
    edited = client.put(
        f"/api/v1/community/reviews/{title.slug}/",
        {"body": "An edited review that needs moderation again.", "contains_spoilers": False},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "pending"
    assert APIClient().get("/api/v1/community/reviews/").json()["count"] == 0


@pytest.mark.django_db
def test_review_links_only_to_an_opted_in_public_profile(community_data):
    first, _, title = community_data
    review = TitleReview.objects.create(
        user=first,
        title=title,
        body="An approved review that can identify its public author.",
        status=TitleReview.Status.APPROVED,
        published_at=timezone.now(),
    )
    response = APIClient().get("/api/v1/community/reviews/").json()["results"][0]
    assert response["author_public_id"] is None

    first.profile_is_public = True
    first.save(update_fields=["profile_is_public"])
    response = APIClient().get("/api/v1/community/reviews/").json()["results"][0]
    assert response["author_public_id"] == str(first.public_id)
    assert response["id"] == review.id


@pytest.mark.django_db
def test_review_author_without_a_display_name_exposes_no_internal_id(community_data):
    """A missing display name must not fall back to the account's primary key.

    Email registration leaves `display_name` optional, so the fallback used to put
    the internal id into a public payload — revealing registration order and a
    rough user count, for exactly the reviewers whose `public_id` is withheld.
    The client renders its own localized placeholder for an empty name.
    """
    author = User.objects.create_user(
        email="nameless@example.com", password="A-strong-passphrase-2042"
    )
    _, _, title = community_data
    TitleReview.objects.create(
        user=author,
        title=title,
        body="An approved review written by someone with no display name.",
        status=TitleReview.Status.APPROVED,
        published_at=timezone.now(),
    )
    payload = APIClient().get("/api/v1/community/reviews/").json()["results"][0]
    assert payload["author_name"] == ""
    assert payload["author_public_id"] is None
    # The removed fallback rendered the primary key as "AniCast #<pk>".
    assert "AniCast #" not in str(payload)
    assert f"AniCast #{author.pk}" not in payload["author_name"]


@pytest.mark.django_db
def test_deactivating_an_account_withdraws_its_public_reviews(community_data):
    """Deactivation is the takedown mechanism, so it must reach published content.

    It already hides the profile and blocks following; leaving reviews readable on
    every title page made the takedown partial.
    """
    first, _, title = community_data
    TitleReview.objects.create(
        user=first,
        title=title,
        body="An approved review that must disappear with its author.",
        status=TitleReview.Status.APPROVED,
        published_at=timezone.now(),
    )
    client = APIClient()
    assert client.get("/api/v1/community/reviews/").json()["count"] == 1
    assert len(client.get(f"/api/v1/titles/{title.slug}/community/").json()["reviews"]) == 1

    first.is_active = False
    first.save(update_fields=["is_active"])

    assert client.get("/api/v1/community/reviews/").json()["count"] == 0
    assert client.get(f"/api/v1/titles/{title.slug}/community/").json()["reviews"] == []


@pytest.mark.django_db
def test_deactivating_an_account_withdraws_its_public_collections(community_data):
    first, _, title = community_data
    collection = TitleCollection.objects.create(
        owner=first, name="Public picks", slug="public-picks", is_public=True
    )
    TitleCollectionItem.objects.create(collection=collection, title=title, position=0)
    url = f"/api/v1/public/collections/{first.public_id}/{collection.slug}/"
    client = APIClient()
    assert client.get(url).status_code == 200

    first.is_active = False
    first.save(update_fields=["is_active"])

    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_public_profile_exposes_only_approved_and_explicitly_public_content(community_data):
    first, _, title = community_data
    assert APIClient().get(f"/api/v1/public/users/{first.public_id}/").status_code == 404
    first.profile_is_public = True
    first.bio = "Профиль для теста безопасной социальной витрины."
    first.save(update_fields=["profile_is_public", "bio"])

    public_collection = TitleCollection.objects.create(
        owner=first, name="Public picks", slug="public-picks", description="Visible", is_public=True
    )
    private_collection = TitleCollection.objects.create(
        owner=first, name="Private picks", slug="private-picks", is_public=False
    )
    TitleCollectionItem.objects.create(collection=public_collection, title=title, position=0)
    TitleReview.objects.create(
        user=first,
        title=title,
        body="An approved review that belongs on the public profile.",
        status=TitleReview.Status.APPROVED,
        published_at=timezone.now(),
    )
    TitleReview.objects.create(
        user=first,
        title=Title.objects.create(name="Pending title", slug="pending-profile-title"),
        body="A pending review that must remain private from the profile.",
    )

    response = APIClient().get(f"/api/v1/public/users/{first.public_id}/")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    assert body["profile"] == {
        "public_id": str(first.public_id),
        "display_name": "First",
        "bio": "Профиль для теста безопасной социальной витрины.",
    }
    assert body["stats"] == {"collections": 1, "reviews": 1, "followers": 0}
    assert [collection["name"] for collection in body["collections"]] == ["Public picks"]
    assert body["collections"][0]["item_count"] == 1
    assert body["collections"][0]["preview_titles"][0]["slug"] == title.slug
    assert len(body["reviews"]) == 1
    serialized = str(body)
    assert first.email not in serialized
    assert private_collection.name not in serialized
    assert "pending review" not in serialized


@pytest.mark.django_db
def test_follow_requires_public_target_rejects_self_and_is_idempotent(community_data):
    first, second, _ = community_data
    client = APIClient()
    client.force_login(first)
    path = f"/api/v1/community/follows/{second.public_id}/"
    assert client.put(path).status_code == 404

    second.profile_is_public = True
    second.save(update_fields=["profile_is_public"])
    assert client.put(path).status_code == 201
    assert client.put(path).status_code == 200
    assert ProfileFollow.objects.count() == 1
    state = client.get(path).json()
    assert state == {"is_self": False, "is_following": True, "followers": 1}
    assert client.get(path)["Cache-Control"] == "no-store, private"

    first.profile_is_public = True
    first.save(update_fields=["profile_is_public"])
    assert client.put(f"/api/v1/community/follows/{first.public_id}/").status_code == 400
    assert client.delete(path).status_code == 204
    assert not ProfileFollow.objects.exists()


@pytest.mark.django_db
def test_follow_mutation_requires_auth_and_csrf(community_data):
    first, second, _ = community_data
    second.profile_is_public = True
    second.save(update_fields=["profile_is_public"])
    path = f"/api/v1/community/follows/{second.public_id}/"
    assert APIClient().put(path).status_code in {401, 403}
    checked = APIClient(enforce_csrf_checks=True)
    checked.force_login(first)
    assert checked.put(path).status_code == 403


@pytest.mark.django_db
def test_following_feed_contains_only_safe_content_from_followed_public_profiles(community_data):
    follower, followed, title = community_data
    unrelated = User.objects.create_user(email="unrelated-feed@example.com", display_name="Unrelated", profile_is_public=True)
    followed.profile_is_public = True
    followed.save(update_fields=["profile_is_public"])
    ProfileFollow.objects.create(follower=follower, following=followed)
    TitleReview.objects.create(
        user=followed,
        title=title,
        body="Approved followed review with enough useful detail.",
        status=TitleReview.Status.APPROVED,
        published_at=timezone.now(),
    )
    TitleReview.objects.create(
        user=unrelated,
        title=Title.objects.create(name="Unrelated title", slug="unrelated-feed-title"),
        body="Approved but unrelated review with enough useful detail.",
        status=TitleReview.Status.APPROVED,
        published_at=timezone.now(),
    )
    TitleReview.objects.create(
        user=followed,
        title=Title.objects.create(name="Pending feed title", slug="pending-feed-title"),
        body="Pending followed review that must remain private.",
    )
    TitleCollection.objects.create(owner=followed, name="Visible feed list", slug="visible-feed", is_public=True)
    TitleCollection.objects.create(owner=followed, name="Private feed list", slug="private-feed", is_public=False)

    client = APIClient()
    client.force_login(follower)
    response = client.get("/api/v1/community/feed/")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, private"
    body = response.json()
    assert body["count"] == 2
    assert {item["kind"] for item in body["results"]} == {"review", "collection"}
    serialized = str(body)
    assert "Approved followed review" in serialized
    assert "Visible feed list" in serialized
    assert "Unrelated" not in serialized
    assert "Pending followed" not in serialized
    assert "Private feed list" not in serialized


@pytest.mark.django_db
def test_closing_profile_revokes_incoming_follows(community_data):
    follower, target, _ = community_data
    target.profile_is_public = True
    target.save(update_fields=["profile_is_public"])
    ProfileFollow.objects.create(follower=follower, following=target)
    client = APIClient()
    client.force_login(target)
    response = client.put(
        "/api/v1/account/profile/",
        {"display_name": target.display_name, "bio": "", "profile_is_public": False},
        format="json",
    )
    assert response.status_code == 200
    assert not ProfileFollow.objects.exists()


@pytest.mark.django_db
def test_review_requires_auth_csrf_and_minimum_length(community_data):
    first, _, title = community_data
    assert APIClient().put(f"/api/v1/community/reviews/{title.slug}/", {"body": "Long enough review text."}, format="json").status_code in {401, 403}
    client = APIClient()
    client.force_login(first)
    assert client.put(f"/api/v1/community/reviews/{title.slug}/", {"body": "short"}, format="json").status_code == 400
    checked = APIClient(enforce_csrf_checks=True)
    checked.force_login(first)
    assert checked.put(f"/api/v1/community/reviews/{title.slug}/", {"body": "Long enough review text."}, format="json").status_code == 403


@pytest.mark.django_db
def test_staff_approval_sets_moderator_and_audit_log(community_data, client):
    first, _, title = community_data
    staff = User.objects.create_superuser(email="community-admin@example.com", password="A-strong-admin-passphrase-2042")
    review = TitleReview.objects.create(user=first, title=title, body="A review waiting for staff approval.")
    client.force_login(staff)
    response = client.post(
        reverse("admin:community_titlereview_changelist"),
        {"action": "approve_reviews", "_selected_action": [str(review.pk)], "index": "0"},
    )
    assert response.status_code == 302
    review.refresh_from_db()
    assert review.status == TitleReview.Status.APPROVED
    assert review.moderated_by == staff
    assert review.published_at is not None
    assert LogEntry.objects.filter(object_id=str(review.pk), action_flag=CHANGE).exists()
