from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import (
    Episode,
    EpisodeTranslation,
    Character,
    CharacterTranslation,
    Franchise,
    FranchiseTranslation,
    Genre,
    GenreTranslation,
    Provider,
    RightsGrant,
    Source,
    SourceReport,
    MediaAsset,
    Title,
    TitleTranslation,
    TitleCharacter,
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
    provider = Provider.objects.create(
        name="Provider Registry",
        slug="provider-registry",
        is_enabled=True,
        allowed_hosts=["example.invalid"],
        playback_adapter="external_link",
    )
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
    assert response.json()["mode"] == "external_link"
    assert response.json()["url"].startswith("/api/v1/playback/")
    assert source.url not in response.json()["url"]
    assert response["Cache-Control"] == "no-store, private"
    redirect = APIClient().get(response.json()["url"])
    assert redirect.status_code == 302
    assert redirect.url == source.url
    assert redirect["Referrer-Policy"] == "no-referrer"
    grant.status = "revoked"
    grant.save(update_fields=["status"])
    assert APIClient().get(f"/api/v1/sources/{source.id}/playback/").status_code == 404


@pytest.fixture
def authorized_source(db):
    title = Title.objects.create(name="Playback Test", slug="playback-test")
    episode = Episode.objects.create(title=title, number=1)
    provider = Provider.objects.create(
        name="Playback Provider",
        slug="playback-provider",
        is_enabled=True,
        allowed_hosts=["watch.example.com"],
        playback_adapter="external_link",
    )
    source = Source.objects.create(
        episode=episode,
        provider=provider,
        name="Playback Source",
        url="https://watch.example.com/episode/1",
    )
    approver = User.objects.create_user(email="playback-rights@example.com", password="A-strong-passphrase-2042")
    now = timezone.now()
    grant = RightsGrant.objects.create(
        source=source,
        status=RightsGrant.Status.ACTIVE,
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=1),
        contract_reference="PLAYBACK-CONTRACT",
        approved_by=approver,
        approved_at=now,
    )
    return source, provider, grant


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("availability", "unavailable"),
        ("url", "http://watch.example.com/episode/1"),
        ("url", "https://user:password@watch.example.com/episode/1"),
        ("url", "https://evil.example.com/episode/1"),
        ("url", "https://watch.example.com:444/episode/1"),
        ("url", "https://watch.example.com/episode/1#redirect"),
    ],
)
def test_playback_rejects_unsafe_or_unavailable_source(authorized_source, field, value):
    source, _, _ = authorized_source
    setattr(source, field, value)
    source.save(update_fields=[field])
    assert APIClient().get(f"/api/v1/sources/{source.id}/playback/").status_code == 404


@pytest.mark.django_db
def test_playback_rejects_unknown_adapter_disabled_provider_and_invalid_config(authorized_source):
    source, provider, _ = authorized_source
    endpoint = f"/api/v1/sources/{source.id}/playback/"
    provider.playback_adapter = "missing"
    provider.save(update_fields=["playback_adapter"])
    assert APIClient().get(endpoint).status_code == 404
    provider.playback_adapter = "external_link"
    provider.playback_config = {"token": "must-not-be-stored"}
    provider.save(update_fields=["playback_adapter", "playback_config"])
    assert APIClient().get(endpoint).status_code == 404
    provider.playback_config = {}
    provider.is_enabled = False
    provider.save(update_fields=["playback_config", "is_enabled"])
    assert APIClient().get(endpoint).status_code == 404


@pytest.mark.django_db
def test_playback_rejects_inactive_or_unapproved_rights(authorized_source):
    source, _, grant = authorized_source
    endpoint = f"/api/v1/sources/{source.id}/playback/"
    grant.approved_at = None
    grant.save(update_fields=["approved_at"])
    assert APIClient().get(endpoint).status_code == 404
    grant.approved_at = timezone.now()
    grant.valid_from = timezone.now() + timedelta(minutes=1)
    grant.valid_until = timezone.now() + timedelta(hours=1)
    grant.save(update_fields=["approved_at", "valid_from", "valid_until"])
    assert APIClient().get(endpoint).status_code == 404
    grant.valid_from = timezone.now() - timedelta(hours=2)
    grant.valid_until = timezone.now() - timedelta(hours=1)
    grant.save(update_fields=["valid_from", "valid_until"])
    assert APIClient().get(endpoint).status_code == 404


@pytest.mark.django_db
def test_playback_token_is_tamper_proof_expires_and_rechecks_authorization(authorized_source, monkeypatch, settings):
    source, provider, grant = authorized_source
    settings.PLAYBACK_URL_TTL_SECONDS = 1
    monkeypatch.setattr("django.core.signing.time.time", lambda: 1_000)
    issued = APIClient().get(f"/api/v1/sources/{source.id}/playback/")
    url = issued.json()["url"]
    tampered_url = f"{url[:-2]}{'a' if url[-2] != 'a' else 'b'}/"
    assert APIClient().get(tampered_url).status_code == 404

    source.availability = "unavailable"
    source.save(update_fields=["availability"])
    assert APIClient().get(url).status_code == 404
    source.availability = "available"
    source.save(update_fields=["availability"])

    provider.is_enabled = False
    provider.save(update_fields=["is_enabled"])
    assert APIClient().get(url).status_code == 404
    provider.is_enabled = True
    provider.save(update_fields=["is_enabled"])

    source.url = "https://evil.example.com/redirect"
    source.save(update_fields=["url"])
    assert APIClient().get(url).status_code == 404
    source.url = "https://watch.example.com/episode/1"
    source.save(update_fields=["url"])

    grant.status = RightsGrant.Status.REVOKED
    grant.save(update_fields=["status"])
    assert APIClient().get(url).status_code == 404
    grant.status = RightsGrant.Status.ACTIVE
    grant.save(update_fields=["status"])
    monkeypatch.setattr("django.core.signing.time.time", lambda: 1_002)
    assert APIClient().get(url).status_code == 404


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


@pytest.mark.django_db
def test_character_list_detail_and_translations(catalog_data):
    character = Character.objects.create(name="Hero", slug="hero", original_name="ヒーロー")
    CharacterTranslation.objects.create(character=character, language="ru", name="Герой", description="Главный герой")
    TitleCharacter.objects.create(title=catalog_data, character=character, role="protagonist")
    listing = APIClient().get("/api/v1/characters/")
    assert listing.status_code == 200
    assert listing.json()["results"][0]["name"] == "Герой"
    detail = APIClient().get("/api/v1/characters/hero/")
    assert detail.json()["title_count"] == 1
    assert detail.json()["title_links"][0]["role"] == "protagonist"
    english = APIClient().get("/api/v1/characters/hero/?lang=en")
    assert english.json()["name"] == "Hero"
    assert APIClient().get("/api/v1/characters/?q=Герой").json()["count"] == 1


@pytest.mark.django_db
def test_media_api_only_exposes_published_rights_attributed_assets(catalog_data):
    draft = MediaAsset.objects.create(
        title=catalog_data, kind="image", url="https://example.invalid/draft.jpg",
        credit="Studio", rights_reference="RIGHTS-1", is_published=False,
    )
    published = MediaAsset.objects.create(
        title=catalog_data, kind="trailer", url="https://example.invalid/trailer",
        credit="Studio", rights_reference="RIGHTS-2", is_published=True,
    )
    response = APIClient().get("/api/v1/media/")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["id"] == published.id
    assert response.json()["results"][0]["id"] != draft.id
    assert APIClient().get("/api/v1/media/?kind=unknown").status_code == 400


@pytest.mark.django_db
def test_similar_titles_rank_shared_genres_and_franchise(catalog_data):
    action = Genre.objects.get(slug="action")
    sibling = Title.objects.create(name="Saga Next", slug="saga-next", franchise=catalog_data.franchise)
    sibling.genres.add(action)
    partial = Title.objects.create(name="Partial", slug="partial")
    partial.genres.add(action)
    unrelated = Title.objects.create(name="Unrelated", slug="unrelated")
    response = APIClient().get(f"/api/v1/titles/{catalog_data.slug}/similar/")
    assert response.status_code == 200
    slugs = [item["slug"] for item in response.json()]
    assert catalog_data.slug not in slugs
    assert unrelated.slug not in slugs
    assert slugs.index("saga-next") < slugs.index("partial")
    assert len(slugs) <= 12


@pytest.mark.django_db
def test_similar_titles_franchise_fallback_without_genres(catalog_data):
    catalog_data.genres.clear()
    Title.objects.create(name="Franchise Mate", slug="franchise-mate", franchise=catalog_data.franchise)
    response = APIClient().get(f"/api/v1/titles/{catalog_data.slug}/similar/")
    assert response.status_code == 200
    slugs = [item["slug"] for item in response.json()]
    assert slugs == ["franchise-mate"]


@pytest.mark.django_db
def test_similar_titles_empty_without_genres_and_franchise(db):
    Title.objects.create(name="Lonely", slug="lonely")
    Title.objects.create(name="Other", slug="other")
    response = APIClient().get("/api/v1/titles/lonely/similar/")
    assert response.status_code == 200
    assert response.json() == []
    assert APIClient().get("/api/v1/titles/missing/similar/").status_code == 404


@pytest.mark.django_db
def test_fetch_shikimori_mapping_helpers():
    from catalog.management.commands.fetch_shikimori import (
        build_genre,
        build_title,
        clean_description,
        episode_count,
        map_kind,
        map_status,
    )

    entry = {
        "id": 16498,
        "name": "Shingeki no Kyojin",
        "russian": "Атака титанов",
        "kind": "tv_24",
        "status": "released",
        "episodes": 25,
        "episodes_aired": 25,
        "aired_on": "2013-04-07",
        "image": {"original": "/system/animes/original/16498.jpg?1711973439"},
    }
    detail = {
        "description": "[b]Люди[/b] против [i]титанов[/i].",
        "english": ["Attack on Titan"],
        "japanese": ["進撃の巨人"],
        "genres": [
            {"id": 1, "name": "Action", "russian": "Экшен"},
            {"id": 27, "name": "Shounen", "russian": "Сёнэн"},
        ],
    }
    title = build_title(entry, detail)
    assert title["slug"] == "16498-shingeki-no-kyojin"
    assert title["name"] == "Атака титанов"
    assert title["original_name"] == "進撃の巨人"
    assert title["synopsis"] == "Люди против титанов."
    assert title["title_type"] == "anime"
    assert title["status"] == "finished"
    assert title["year"] == 2013
    assert title["poster_url"].startswith("https://shikimori.io/system/")
    assert title["genres"] == ["action", "shounen"]
    assert title["translations"]["en"]["name"] == "Attack on Titan"
    assert title["translations"]["ru"]["name"] == "Атака титанов"
    assert len(title["episodes"]) == 25
    assert title["episodes"][0] == {"number": 1}

    assert episode_count({"status": "anons", "episodes": 12}) == 0
    assert episode_count({"status": "ongoing", "episodes": 24, "episodes_aired": 12}) == 12
    assert map_kind("ona") == "ova"
    assert map_kind("music") == "special"
    assert map_status("ongoing") == "ongoing"
    assert clean_description("[b]x[/b] [url=y]z[/url]") == "x z"
    assert build_genre({"id": 5, "name": "Drama", "russian": "Драма"})["translations"]["ru"]["name"] == "Драма"


@pytest.mark.django_db
def test_fetch_shikimori_character_and_franchise_helpers():
    from catalog.management.commands.fetch_shikimori import (
        build_character,
        build_franchises,
        character_slug,
        map_role,
    )

    role_entry = {"rolesEn": ["Main"], "character": {"id": 40882, "name": "Eren Yeager", "russian": "Эрен Йегер"}}
    detail = {
        "japanese": "エレン・イェーガー",
        "description": "[b]Главный герой[/b].",
        "image": {"original": "/system/characters/original/40882.jpg?1"},
    }
    character = build_character(role_entry, detail)
    assert character["slug"] == "40882-eren-yeager"
    assert character["name"] == "Эрен Йегер"
    assert character["original_name"] == "エレン・イェーガー"
    assert character["description"] == "Главный герой."
    assert character["image_url"].startswith("https://shikimori.io/system/")
    assert character["translations"]["en"]["name"] == "Eren Yeager"

    assert map_role(["Main"]) == "protagonist"
    assert map_role(["Supporting"]) == "supporting"
    assert map_role([]) == "supporting"
    assert character_slug({"id": 7, "name": "Levi"}) == "7-levi"

    titles = [
        {"slug": "b-2", "name": "Берсерк 2", "year": 2016, "translations": {"en": {"name": "Berserk 2"}}},
        {"slug": "b-1", "name": "Берсерк", "year": 1997, "translations": {"en": {"name": "Berserk"}}},
    ]
    franchises = build_franchises(titles, {"b-1": "berserk", "b-2": "berserk"})
    assert len(franchises) == 1
    assert franchises[0]["slug"] == "berserk"
    assert franchises[0]["name"] == "Берсерк"
    assert franchises[0]["translations"]["en"]["name"] == "Berserk"


@pytest.mark.django_db
def test_import_catalog_applies_characters_and_links():
    from catalog.management.commands.import_catalog import apply_payload, validate_payload

    payload = {
        "characters": [
            {
                "slug": "40882-eren-yeager",
                "name": "Эрен Йегер",
                "original_name": "エレン・イェーガー",
                "description": "Главный герой.",
                "image_url": "https://shikimori.one/system/characters/original/40882.jpg",
                "translations": {"en": {"name": "Eren Yeager"}},
            }
        ],
        "titles": [
            {
                "slug": "16498-shingeki-no-kyojin",
                "name": "Атака титанов",
                "characters": [
                    {"character": "40882-eren-yeager", "role": "protagonist", "sort_order": 0},
                    {"character": "40882-eren-yeager", "role": "supporting", "sort_order": 1},
                ],
            }
        ],
    }
    with pytest.raises(Exception, match="повторяющийся персонаж"):
        validate_payload(payload)
    payload["titles"][0]["characters"] = payload["titles"][0]["characters"][:1]
    validate_payload(payload)
    stats = apply_payload(payload)
    assert stats["characters"] == 1
    assert stats["title_characters"] == 1
    link = TitleCharacter.objects.select_related("title", "character").get()
    assert link.title.slug == "16498-shingeki-no-kyojin"
    assert link.character.slug == "40882-eren-yeager"
    assert link.role == "protagonist"

    payload["titles"][0]["characters"] = [{"character": "missing", "role": "supporting"}]
    with pytest.raises(Exception, match="не найден"):
        apply_payload(payload)
