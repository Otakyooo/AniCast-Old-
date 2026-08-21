from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import (
    Episode,
    EpisodeTranslation,
    Franchise,
    FranchiseTranslation,
    Genre,
    GenreTranslation,
    Provider,
    RightsGrant,
    Source,
    SourceReport,
    Title,
    TitleTranslation,
)


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
    assert "url" not in body["episodes"][0]["sources"][0]
    assert body["episodes"][0]["sources"][0]["playback_available"] is False


@pytest.mark.django_db
def test_title_detail_is_read_only_and_bounded_page_size(catalog_data):
    client = APIClient()
    assert client.post("/api/v1/titles/", {}).status_code == 405
    response = client.get("/api/v1/titles/?page_size=999")
    assert response.status_code == 200
    assert response.json()["results"]


@pytest.mark.django_db
def test_schedule_defaults_to_seven_days_and_orders_episodes(catalog_data):
    today = timezone.localdate()
    catalog_data.episodes.update(air_date=today)
    later = Episode.objects.create(title=catalog_data, number=2, name="Later", air_date=today + timedelta(days=6))
    Episode.objects.create(title=catalog_data, number=3, name="Outside", air_date=today + timedelta(days=7))
    response = APIClient().get("/api/v1/schedule/")
    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert [item["id"] for item in response.json()["results"]] == [catalog_data.episodes.get(number=1).id, later.id]
    assert response.json()["results"][0]["title"]["slug"] == "sky-test"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "from=invalid",
        "from=2026-08-21&to=2026-08-20",
        "from=2026-08-01&to=2026-09-01",
    ],
)
def test_schedule_rejects_invalid_or_unbounded_ranges(query):
    response = APIClient().get(f"/api/v1/schedule/?{query}")
    assert response.status_code == 400


@pytest.mark.django_db
def test_source_reports_require_auth_and_are_private(catalog_data):
    source = Source.objects.get(episode__title=catalog_data)
    client = APIClient()
    assert client.post("/api/v1/source-reports/", {"source": source.id, "reason": "unavailable"}).status_code in {401, 403}
    first = User.objects.create_user(email="first@example.com", password="A-strong-passphrase-2042")
    second = User.objects.create_user(email="second@example.com", password="A-strong-passphrase-2042")
    SourceReport.objects.create(source=source, reporter=second, reason="quality")
    client.force_login(first)
    created = client.post(
        "/api/v1/source-reports/",
        {"source": source.id, "reason": "unavailable", "message": "Returns an error"},
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["title_slug"] == "sky-test"
    listing = client.get("/api/v1/source-reports/")
    assert listing.status_code == 200
    assert listing.json()["count"] == 1


@pytest.mark.django_db
def test_duplicate_open_report_and_empty_other_reason_are_rejected(catalog_data):
    source = Source.objects.get(episode__title=catalog_data)
    user = User.objects.create_user(email="viewer@example.com", password="A-strong-passphrase-2042")
    client = APIClient()
    client.force_login(user)
    payload = {"source": source.id, "reason": "unavailable"}
    assert client.post("/api/v1/source-reports/", payload, format="json").status_code == 201
    assert client.post("/api/v1/source-reports/", payload, format="json").status_code == 400
    assert client.post(
        "/api/v1/source-reports/",
        {"source": source.id, "reason": "other", "message": ""},
        format="json",
    ).status_code == 400


@pytest.mark.django_db
def test_playback_is_fail_closed_and_requires_active_approved_right(catalog_data):
    source = Source.objects.get(episode__title=catalog_data)
    assert APIClient().get(f"/api/v1/sources/{source.id}/playback/").status_code == 404
    provider = Provider.objects.create(name="Provider Registry", slug="provider-registry", is_enabled=True, allowed_hosts=["example.invalid"])
    source.provider = provider
    source.save(update_fields=["provider"])
    approver = User.objects.create_user(email="rights@example.com", password="A-strong-passphrase-2042")
    now = timezone.now()
    grant = RightsGrant.objects.create(
        source=source,
        status="active",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
        contract_reference="CONTRACT-1",
        approved_by=approver,
        approved_at=now,
    )
    response = APIClient().get(f"/api/v1/sources/{source.id}/playback/")
    assert response.status_code == 200
    assert response.json()["url"] == source.url
    grant.status = "revoked"
    grant.save(update_fields=["status"])
    assert APIClient().get(f"/api/v1/sources/{source.id}/playback/").status_code == 404


@pytest.mark.django_db
def test_franchise_list_and_detail_are_ordered(catalog_data):
    Franchise.objects.create(name="Alpha Editorial", slug="alpha-editorial", sort_order=0)
    response = APIClient().get("/api/v1/franchises/")
    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["results"]][:2] == ["alpha-editorial", "test-franchise"]
    detail = APIClient().get("/api/v1/franchises/test-franchise/")
    assert detail.status_code == 200
    assert detail.json()["title_count"] == 1
    assert detail.json()["titles"][0]["slug"] == "sky-test"
    assert APIClient().get("/api/v1/franchises/missing/").status_code == 404


@pytest.mark.django_db
def test_catalog_localizes_content_and_searches_translations(catalog_data):
    genre = Genre.objects.get(slug="action")
    franchise = catalog_data.franchise
    episode = catalog_data.episodes.get(number=1)
    GenreTranslation.objects.create(genre=genre, language="ru", name="Экшен")
    FranchiseTranslation.objects.create(franchise=franchise, language="ru", name="Тестовая франшиза", description="Описание")
    TitleTranslation.objects.create(title=catalog_data, language="ru", name="Небесный тест", synopsis="Русское описание")
    EpisodeTranslation.objects.create(episode=episode, language="ru", name="Начало", synopsis="Первый эпизод")

    russian = APIClient().get("/api/v1/titles/sky-test/")
    assert russian.json()["name"] == "Небесный тест"
    assert russian.json()["genres"][0]["name"] == "Экшен"
    assert russian.json()["franchise"]["name"] == "Тестовая франшиза"
    assert russian.json()["episodes"][0]["name"] == "Начало"

    english = APIClient().get("/api/v1/titles/sky-test/?lang=en")
    assert english.json()["name"] == "Sky Test"
    search = APIClient().get("/api/v1/titles/?q=Небесный")
    assert search.json()["count"] == 1


@pytest.mark.django_db
def test_language_cookie_and_unsupported_language_fallback(catalog_data):
    TitleTranslation.objects.create(title=catalog_data, language="ru", name="Русское имя")
    client = APIClient()
    client.cookies["anicast_lang"] = "en"
    assert client.get("/api/v1/titles/sky-test/").json()["name"] == "Sky Test"
    assert client.get("/api/v1/titles/sky-test/?lang=xx").json()["name"] == "Русское имя"
