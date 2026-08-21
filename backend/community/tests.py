import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Title
from community.models import TitleReview


@pytest.fixture
def community_data(db):
    first = User.objects.create_user(email="first-community@example.com", password="A-strong-passphrase-2042", display_name="First")
    second = User.objects.create_user(email="second-community@example.com", password="A-strong-passphrase-2042", display_name="Second")
    title = Title.objects.create(name="Community Title", slug="community-title")
    return first, second, title


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
