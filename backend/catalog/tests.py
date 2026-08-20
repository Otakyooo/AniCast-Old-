import pytest
from rest_framework.test import APIClient

from catalog.models import Episode, Franchise, Genre, Source, Title


@pytest.fixture
def catalog_data(db):
    action = Genre.objects.create(name="Action", slug="action")
    drama = Genre.objects.create(name="Drama", slug="drama")
    franchise = Franchise.objects.create(name="Test Franchise", slug="test-franchise")
    title = Title.objects.create(
        name="Sky Test", slug="sky-test", original_name="Sky Test Original",
        status="ongoing", title_type="anime", franchise=franchise,
    )
    title.genres.add(action, drama)
    episode = Episode.objects.create(title=title, number=1, name="Beginning")
    Source.objects.create(episode=episode, name="Provider", kind="sub", url="https://example.invalid/1")
    return title


@pytest.mark.django_db
def test_title_list_filters_and_paginates(catalog_data):
    response = APIClient().get("/api/v1/titles/?q=sky&genre=action&status=ongoing&type=anime&page_size=1")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["slug"] == "sky-test"


@pytest.mark.django_db
def test_title_detail_includes_nested_relations(catalog_data):
    response = APIClient().get("/api/v1/titles/sky-test/")
    body = response.json()
    assert response.status_code == 200
    assert body["franchise"]["slug"] == "test-franchise"
    assert body["genres"][0]["slug"] == "action"
    assert body["episodes"][0]["sources"][0]["availability"] == "available"
    assert body["episodes"][0]["sources"][0]["is_available"] is True


@pytest.mark.django_db
def test_title_detail_is_read_only_and_bounded_page_size(catalog_data):
    client = APIClient()
    assert client.post("/api/v1/titles/", {}).status_code == 405
    response = client.get("/api/v1/titles/?page_size=999")
    assert response.status_code == 200
    assert response.json()["results"]
