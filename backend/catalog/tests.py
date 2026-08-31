from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from community.models import TitleRating
from library.models import LibraryEntry
from catalog.models import (
    Episode,
    EpisodeTranslation,
    Character,
    CharacterTranslation,
    Creator,
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
    TitleCredit,
)
from django.core.management import call_command


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
    assert body["franchise"] == {"name": "Test Franchise", "slug": "test-franchise"}
    assert body["genres"][0]["slug"] == "action"
    assert body["episodes_count"] == 1
    assert body["episodes"][0]["sources"][0]["availability"] == "available"
    assert body["episodes"][0]["sources"][0]["is_available"] is True
    assert "url" not in body["episodes"][0]["sources"][0]
    assert body["episodes"][0]["sources"][0]["playback_available"] is False


@pytest.mark.django_db
def test_creator_detail_lists_credited_titles(catalog_data):
    creator = Creator.objects.create(
        name="Тестовый режиссёр",
        slug="тестовый-режиссёр",
        image_url="https://shikimori.one/system/people/original/1.jpg",
    )
    TitleCredit.objects.create(
        title=catalog_data,
        creator=creator,
        role="director",
        sort_order=0,
    )

    response = APIClient().get("/api/v1/creators/тестовый-режиссёр/")

    assert response.status_code == 200
    assert response.json()["slug"] == "тестовый-режиссёр"
    assert response.json()["image_url"] == ""
    assert response.json()["title_credits"][0]["role"] == "director"
    assert response.json()["title_credits"][0]["title"]["slug"] == "sky-test"
    title = APIClient().get("/api/v1/titles/sky-test/").json()
    assert title["credits"][0]["creator"]["image_url"] == ""
    assert "shikimori" not in str(title).lower()


@pytest.mark.django_db
def test_title_detail_paginates_episodes(catalog_data):
    Episode.objects.create(title=catalog_data, number=2, name="Second")
    Episode.objects.create(title=catalog_data, number=3, name="Third")
    client = APIClient()
    unpaginated = client.get("/api/v1/titles/sky-test/").json()
    assert [episode["number"] for episode in unpaginated["episodes"]] == [1, 2, 3]
    first = client.get("/api/v1/titles/sky-test/?episodes_page_size=2").json()
    assert first["episodes_count"] == 3
    assert [episode["number"] for episode in first["episodes"]] == [1, 2]
    second = client.get("/api/v1/titles/sky-test/?episodes_page_size=2&episodes_page=2").json()
    assert [episode["number"] for episode in second["episodes"]] == [3]
    beyond = client.get("/api/v1/titles/sky-test/?episodes_page=999")
    assert beyond.status_code == 404
    oversized = client.get("/api/v1/titles/sky-test/?episodes_page_size=500").json()
    assert len(oversized["episodes"]) == 3


@pytest.mark.django_db
def test_title_detail_compact_episode_rows_omit_playback_sources(catalog_data):
    body = APIClient().get(
        "/api/v1/titles/sky-test/?episodes_page=1&episodes_page_size=20&episode_sources=0"
    ).json()
    assert body["episodes"][0]["number"] == 1
    assert "sources" not in body["episodes"][0]


@pytest.mark.django_db
def test_title_episode_detail_returns_single_episode(catalog_data):
    client = APIClient()
    response = client.get("/api/v1/titles/sky-test/episodes/1/")
    assert response.status_code == 200
    body = response.json()
    assert body["number"] == 1
    assert body["title"]["slug"] == "sky-test"
    assert body["sources"][0]["playback_available"] is False
    assert "url" not in body["sources"][0]
    assert client.get("/api/v1/titles/sky-test/episodes/999/").status_code == 404
    assert client.get("/api/v1/titles/missing/episodes/1/").status_code == 404


@pytest.mark.django_db
def test_watch_navigation_groups_playable_sources_by_voice_over(authorized_source, django_assert_max_num_queries):
    first_source, provider, _ = authorized_source
    provider.rights_reference = "Provider catalogue entitlement"
    provider.rights_verified_at = timezone.now()
    provider.save(update_fields=["rights_reference", "rights_verified_at"])
    second_episode = Episode.objects.create(title=first_source.episode.title, number=2)
    Source.objects.create(
        episode=second_episode,
        provider=provider,
        external_id="episode-2",
        name=first_source.name,
        kind=first_source.kind,
        url="https://watch.example.com/episode/2",
    )
    Episode.objects.create(title=first_source.episode.title, number=4)
    Source.objects.create(
        episode=second_episode,
        provider=provider,
        external_id="unavailable-sub",
        name="Subtitle team",
        kind="sub",
        availability="unavailable",
        url="https://watch.example.com/subtitle/2",
    )

    # Title lookup, catalog numbers, provider configuration and authorized
    # source rows stay bounded regardless of the number of episodes.
    with django_assert_max_num_queries(6):
        response = APIClient().get("/api/v1/titles/playback-test/watch-navigation/")

    assert response.status_code == 200
    body = response.json()
    # Catalog metadata keeps its real gaps, while only playable episodes become
    # destinations in the player. The old field remains a compatibility alias.
    assert body["catalog_episode_numbers"] == [1, 2, 4]
    assert body["playable_episode_numbers"] == [1, 2]
    assert body["episode_numbers"] == [1, 2]
    assert len(body["source_groups"]) == 1
    group = body["source_groups"][0]
    assert group["name"] == "Playback Source"
    assert group["kind"] == first_source.kind
    assert group["provider_name"] == "Playback Provider"
    assert group["provider_variant_id"] is None
    assert group["legacy_key"] == group["key"]
    assert group["episode_numbers"] == [1, 2]
    assert group["episodes_count"] == 2
    assert group["popularity_percent"] == 0
    assert "playback_count" not in group
    episode = APIClient().get("/api/v1/titles/playback-test/episodes/1/").json()
    assert episode["sources"][0]["selection_key"] == group["key"]
    assert episode["sources"][0]["provider_name"] == "Playback Provider"
    assert "url" not in group


@pytest.mark.django_db
def test_kodik_watch_key_survives_translation_rename_and_exposes_legacy_alias(authorized_source):
    source, provider, _ = authorized_source
    provider.slug = "kodik"
    provider.name = "Kodik"
    provider.allowed_hosts = ["kodikplayer.com"]
    provider.playback_adapter = "iframe_embed"
    provider.save(update_fields=["slug", "name", "allowed_hosts", "playback_adapter"])
    source.external_id = "serial-1:s1:t610"
    source.name = "Kodik · AniLibria.TV"
    source.url = "https://kodikplayer.com/seria/1/redacted/720p?hide_selectors=true"
    source.save(update_fields=["external_id", "name", "url"])

    client = APIClient()
    before = client.get("/api/v1/titles/playback-test/watch-navigation/").json()["source_groups"][0]
    episode_source = client.get("/api/v1/titles/playback-test/episodes/1/").json()["sources"][0]

    assert before["provider_variant_id"] == "610"
    assert episode_source["provider_variant_id"] == "610"
    assert before["key"] == episode_source["selection_key"]
    assert before["legacy_key"] != before["key"]

    source.name = "Kodik · AniLibria Renamed"
    source.save(update_fields=["name"])
    after = client.get("/api/v1/titles/playback-test/watch-navigation/").json()["source_groups"][0]

    assert after["key"] == before["key"]
    assert after["provider_variant_id"] == before["provider_variant_id"]
    assert after["legacy_key"] != before["legacy_key"]


@pytest.mark.django_db
def test_watch_navigation_returns_404_for_missing_title():
    response = APIClient().get("/api/v1/titles/missing/watch-navigation/")

    assert response.status_code == 404
    assert response.json()["detail"] == "No Title matches the given query."


@pytest.mark.django_db
def test_watch_navigation_exposes_real_catalog_gaps_without_synthesizing_playback():
    title = Title.objects.create(name="Metadata Only", slug="metadata-only")
    Episode.objects.create(title=title, number=2)
    Episode.objects.create(title=title, number=7)

    response = APIClient().get("/api/v1/titles/metadata-only/watch-navigation/")

    assert response.status_code == 200
    assert response.json() == {
        "catalog_episode_numbers": [2, 7],
        "playable_episode_numbers": [],
        "episode_numbers": [],
        "source_groups": [],
    }


@pytest.mark.django_db
def test_watch_navigation_accepts_an_approved_source_level_grant(authorized_source):
    source, _, _ = authorized_source
    body = APIClient().get("/api/v1/titles/playback-test/watch-navigation/").json()
    assert body["source_groups"][0]["episode_numbers"] == [source.episode.number]
    assert body["source_groups"][0]["key"] == APIClient().get(
        "/api/v1/titles/playback-test/episodes/1/"
    ).json()["sources"][0]["selection_key"]


@pytest.mark.django_db
def test_watch_navigation_ranks_sources_by_playback_share(authorized_source):
    source, provider, _ = authorized_source
    provider.rights_reference = "Provider catalogue entitlement"
    provider.rights_verified_at = timezone.now()
    provider.save(update_fields=["rights_reference", "rights_verified_at"])
    source.playback_count = 1
    source.save(update_fields=["playback_count"])
    Source.objects.create(
        episode=source.episode,
        provider=provider,
        external_id="popular-source",
        name="Popular voice",
        kind="dub",
        url="https://watch.example.com/popular/1",
        playback_count=3,
    )

    groups = APIClient().get(
        "/api/v1/titles/playback-test/watch-navigation/"
    ).json()["source_groups"]

    assert [group["name"] for group in groups] == ["Popular voice", "Playback Source"]
    assert [group["popularity_percent"] for group in groups] == [75, 25]
    assert all("playback_count" not in group for group in groups)


@pytest.mark.django_db
def test_title_detail_batches_playback_availability_queries(django_assert_max_num_queries):
    title = Title.objects.create(name="Long Series", slug="long-series")
    provider = Provider.objects.create(
        name="Batch Provider",
        slug="batch-provider",
        is_enabled=True,
        allowed_hosts=["watch.example.com"],
        playback_adapter="external_link",
    )
    approver = User.objects.create_user(email="batch-rights@example.com", password="A-strong-passphrase-2042")
    now = timezone.now()
    for number in range(1, 61):
        episode = Episode.objects.create(title=title, number=number)
        source = Source.objects.create(
            episode=episode,
            provider=provider,
            name="Batch Source",
            url=f"https://watch.example.com/episodes/{number}",
        )
        RightsGrant.objects.create(
            source=source,
            status=RightsGrant.Status.ACTIVE,
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=1),
            contract_reference=f"BATCH-{number}",
            approved_by=approver,
            approved_at=now,
        )

    # Characters, creator credits and related works are all included in one
    # bounded detail payload; the budget protects the endpoint from N+1s.
    with django_assert_max_num_queries(14):
        response = APIClient().get("/api/v1/titles/long-series/?episodes_page_size=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["episodes_count"] == 60
    assert len(payload["episodes"]) == 20
    sources = [source for episode in payload["episodes"] for source in episode["sources"]]
    assert len(sources) == 20
    assert all(source["playback_available"] for source in sources)

    # Without pagination parameters the payload stays backward compatible for the
    # previous frontend release, and still avoids a query per source.
    with django_assert_max_num_queries(12):
        legacy = APIClient().get("/api/v1/titles/long-series/")

    assert len(legacy.json()["episodes"]) == 60


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
def test_schedule_exposes_air_at_and_orders_by_it_within_a_day(catalog_data):
    today = timezone.localdate()
    first = catalog_data.episodes.get(number=1)
    first.air_date = today
    first.air_at = None
    first.save(update_fields=["air_date", "air_at"])
    evening = Episode.objects.create(
        title=catalog_data, number=2, name="Evening",
        air_at=timezone.make_aware(datetime.combine(today, time(21, 30))),
    )
    morning = Episode.objects.create(
        title=catalog_data, number=3, name="Morning",
        air_at=timezone.make_aware(datetime.combine(today, time(9, 0))),
    )
    # Saving an exact moment derives its calendar day, so no separate air_date input.
    assert Episode.objects.get(pk=morning.pk).air_date == today
    results = APIClient().get("/api/v1/schedule/").json()["results"]
    assert [item["id"] for item in results] == [morning.id, evening.id, first.id]
    assert results[0]["air_at"] is not None
    assert results[-1]["air_at"] is None
    assert results[0]["title"]["year"] == catalog_data.year


@pytest.mark.django_db
def test_episode_air_at_keeps_air_date_in_sync(catalog_data):
    episode = catalog_data.episodes.get(number=1)
    moment = timezone.make_aware(datetime.combine(timezone.localdate(), time(22, 15)))
    episode.air_at = moment
    # A partial save of air_at alone must still refresh the derived day.
    episode.save(update_fields=["air_at"])
    episode.refresh_from_db()
    assert episode.air_date == timezone.localtime(moment).date()

    episode.air_at = None
    episode.air_date = None
    episode.save(update_fields=["air_at", "air_date"])
    episode.refresh_from_db()
    # Clearing the moment leaves the day untouched: a day-only episode is valid.
    assert episode.air_at is None
    assert episode.air_date is None


@pytest.mark.django_db
def test_seed_catalog_is_idempotent_and_sets_air_moments():
    call_command("seed_catalog")
    call_command("seed_catalog")
    episodes = Episode.objects.filter(title__slug="demo-title").order_by("number")
    assert [episode.number for episode in episodes] == [1, 2, 3, 4]
    scheduled = [episode for episode in episodes if episode.air_at is not None]
    assert len(scheduled) == 3
    # Saving an exact moment derives the calendar day used by the schedule range.
    for episode in scheduled:
        assert episode.air_date == timezone.localtime(episode.air_at).date()


@pytest.mark.django_db
def test_title_list_ordering_is_opt_in_and_validated(catalog_data):
    client = APIClient()
    popular = Title.objects.create(name="Zeta Popular", slug="zeta-popular", year=2001)
    Title.objects.create(name="Alpha Recent", slug="alpha-recent", year=2030)
    viewer = User.objects.create_user(email="ordering@example.com", password="A-strong-passphrase-2042")
    LibraryEntry.objects.create(user=viewer, title=popular)
    TitleRating.objects.create(user=viewer, title=popular, value=9)

    default_order = [item["slug"] for item in client.get("/api/v1/titles/").json()["results"]]
    assert default_order == sorted(default_order)
    assert client.get("/api/v1/titles/?ordering=popular").json()["results"][0]["slug"] == "zeta-popular"
    assert client.get("/api/v1/titles/?ordering=recent").json()["results"][0]["slug"] == "alpha-recent"
    assert client.get("/api/v1/titles/?ordering=unknown").status_code == 400


@pytest.mark.django_db
def test_title_list_exposes_rating_aggregates_without_per_row_queries(catalog_data):
    client = APIClient()
    unrated = {item["slug"]: item for item in client.get("/api/v1/titles/").json()["results"]}
    assert unrated["sky-test"]["rating_average"] is None
    assert unrated["sky-test"]["rating_count"] == 0

    viewer = User.objects.create_user(email="rater-one@example.com", password="A-strong-passphrase-2042")
    second = User.objects.create_user(email="rater-two@example.com", password="A-strong-passphrase-2042")
    TitleRating.objects.create(user=viewer, title=catalog_data, value=8)
    TitleRating.objects.create(user=second, title=catalog_data, value=9)

    for ordering in ("", "popular", "recent"):
        body = client.get(f"/api/v1/titles/?ordering={ordering}").json()["results"][0]
        assert body["rating_count"] == 2
        assert body["rating_average"] == 8.5

    detail = client.get("/api/v1/titles/sky-test/").json()
    assert detail["rating_count"] == 2
    assert detail["rating_average"] == 8.5


@pytest.mark.django_db
def test_search_and_similar_titles_expose_rating_aggregates(catalog_data):
    viewer = User.objects.create_user(email="rater@example.com", password="A-strong-passphrase-2042")
    TitleRating.objects.create(user=viewer, title=catalog_data, value=7)
    searched = APIClient().get("/api/v1/search/?q=sky").json()["titles"][0]
    assert searched["rating_average"] == 7 and searched["rating_count"] == 1

    other = Title.objects.create(name="Sky Neighbor", slug="sky-neighbor", year=2020)
    other.genres.add(*catalog_data.genres.all())
    related = APIClient().get("/api/v1/titles/sky-test/similar/").json()
    entry = next(item for item in related if item["slug"] == "sky-neighbor")
    assert entry["rating_average"] is None and entry["rating_count"] == 0


@pytest.mark.django_db
def test_global_search_groups_titles_characters_and_franchises(catalog_data):
    character = Character.objects.create(name="Sky Hero", slug="sky-hero")
    TitleCharacter.objects.create(title=catalog_data, character=character)
    Franchise.objects.create(name="Sky Saga", slug="sky-saga")
    client = APIClient()
    assert client.get("/api/v1/search/?q=s").status_code == 400
    assert client.get("/api/v1/search/").status_code == 400
    body = client.get("/api/v1/search/?q=sky").json()
    assert body["query"] == "sky"
    assert [item["slug"] for item in body["titles"]] == ["sky-test"]
    assert [item["slug"] for item in body["characters"]] == ["sky-hero"]
    assert body["franchises"] == []
    assert body["titles"][0]["poster_url"] == catalog_data.poster_url
    empty = client.get("/api/v1/search/?q=nothing-matches").json()
    assert empty["titles"] == [] and empty["characters"] == [] and empty["franchises"] == []


@pytest.mark.django_db
def test_global_search_matches_translated_names(catalog_data):
    TitleTranslation.objects.create(title=catalog_data, language="ru", name="Небесный тест")
    body = APIClient().get("/api/v1/search/?q=Небесный").json()
    assert [item["slug"] for item in body["titles"]] == ["sky-test"]


@pytest.mark.django_db
def test_global_search_bounds_the_query_and_group_sizes(catalog_data):
    for index in range(8):
        Title.objects.create(name=f"Sky Extra {index}", slug=f"sky-extra-{index}")
    body = APIClient().get("/api/v1/search/?q=sky").json()
    assert len(body["titles"]) == 5
    # An oversized term is truncated instead of rejected, so the panel still works.
    long_query = "sky" + "y" * 500
    assert APIClient().get(f"/api/v1/search/?q={long_query}").status_code == 200


@pytest.mark.django_db
def test_franchise_list_supports_search(catalog_data):
    Franchise.objects.create(name="Other Worlds", slug="other-worlds")
    Title.objects.create(name="Sky Sequel", slug="sky-sequel", franchise=catalog_data.franchise)
    results = APIClient().get("/api/v1/franchises/?q=test").json()["results"]
    assert [item["slug"] for item in results] == ["test-franchise"]


@pytest.mark.django_db
def test_title_detail_exposes_cast_without_extra_queries(catalog_data, django_assert_max_num_queries):
    hero = Character.objects.create(name="Hero", slug="hero", image_url="https://example.invalid/hero.jpg")
    rival = Character.objects.create(name="Rival", slug="rival")
    TitleCharacter.objects.create(title=catalog_data, character=hero, role="protagonist", sort_order=0)
    TitleCharacter.objects.create(title=catalog_data, character=rival, role="antagonist", sort_order=1)
    CharacterTranslation.objects.create(character=hero, language="ru", name="Герой")
    # Creator credits and related works extend the payload with a fixed number
    # of prefetches; this remains bounded regardless of cast size.
    with django_assert_max_num_queries(15):
        body = APIClient().get("/api/v1/titles/sky-test/").json()
    assert [entry["character"]["slug"] for entry in body["characters"]] == ["hero", "rival"]
    assert body["characters"][0]["role"] == "protagonist"
    assert body["characters"][0]["character"]["name"] == "Герой"
    assert body["characters"][0]["character"]["image_url"] == ""



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


@pytest.mark.django_db
def test_iframe_playback_uses_signed_resolver_and_rechecks_rights(authorized_source):
    source, provider, grant = authorized_source
    provider.allowed_hosts = ["kodikplayer.com"]
    provider.playback_adapter = "iframe_embed"
    provider.save(update_fields=["allowed_hosts", "playback_adapter"])
    source.url = "https://kodikplayer.com/seria/1/redacted/720p?hide_selectors=true"
    source.save(update_fields=["url"])

    issued = APIClient().get(f"/api/v1/sources/{source.id}/playback/")
    assert issued.status_code == 200
    assert issued.json()["mode"] == "iframe_embed"
    assert issued.json()["url"].startswith("/api/v1/playback/")
    assert source.url not in issued.json()["url"]
    assert provider.playback_config == {}
    episode = APIClient().get("/api/v1/titles/playback-test/episodes/1/").json()
    assert episode["sources"][0]["playback_mode"] == "iframe_embed"
    assert "url" not in episode["sources"][0]
    resolved = APIClient().get(issued.json()["url"])
    assert resolved.status_code == 302
    # Persisting the public player option in Source.url keeps the resolver
    # compatible with the previous pass-through iframe adapter on rollback.
    assert resolved.url == source.url
    source.refresh_from_db()
    assert source.playback_count == 1

    grant.status = RightsGrant.Status.REVOKED
    grant.save(update_fields=["status"])
    assert APIClient().get(issued.json()["url"]).status_code == 404


@pytest.mark.django_db
def test_provider_level_rights_reference_authorizes_sources(catalog_data):
    source = Source.objects.get(episode__title=catalog_data)
    provider = Provider.objects.create(
        name="Kodik", slug="kodik", is_enabled=True,
        allowed_hosts=["kodikplayer.com"], playback_adapter="iframe_embed",
        rights_reference="Kodik account entitlement for anicast.online",
        rights_verified_at=timezone.now(),
    )
    source.provider = provider
    source.url = "https://kodikplayer.com/seria/1/redacted/720p"
    source.save(update_fields=["provider", "url"])
    assert APIClient().get(f"/api/v1/sources/{source.id}/playback/").status_code == 200


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
    # A single title is not useful as a franchise navigation group.
    assert response.json()["results"] == []
    Title.objects.create(name="Sky Sequel", slug="sky-sequel", franchise=catalog_data.franchise)
    response = APIClient().get("/api/v1/franchises/")
    assert [item["slug"] for item in response.json()["results"]] == ["test-franchise"]
    detail = APIClient().get("/api/v1/franchises/test-franchise/")
    assert detail.status_code == 200
    assert detail.json()["title_count"] == 2
    assert [item["slug"] for item in detail.json()["titles"]] == ["sky-sequel", "sky-test"]
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
    assert russian.json()["localized_names"] == {
        "ru": "Небесный тест",
        "en": "Sky Test",
        "ja": "Sky Test Original",
    }
    assert russian.json()["genres"][0]["name"] == "Экшен"
    assert russian.json()["franchise"]["name"] == "Тестовая франшиза"
    assert russian.json()["episodes"][0]["name"] == "Начало"

    english = APIClient().get("/api/v1/titles/sky-test/?lang=en")
    assert english.json()["name"] == "Sky Test"
    search = APIClient().get("/api/v1/titles/?q=Небесный")
    assert search.json()["count"] == 1


@pytest.mark.django_db
def test_title_detail_bounds_large_character_payload(catalog_data):
    for index in range(61):
        character = Character.objects.create(name=f"Cast {index}", slug=f"cast-{index}")
        TitleCharacter.objects.create(title=catalog_data, character=character, sort_order=index)
    first = APIClient().get("/api/v1/titles/sky-test/").json()
    second = APIClient().get("/api/v1/titles/sky-test/?characters_page=2").json()
    assert first["characters_count"] == 61
    assert len(first["characters"]) == 60
    assert len(second["characters"]) == 1


@pytest.mark.django_db
def test_language_cookie_and_unsupported_language_fallback(catalog_data):
    TitleTranslation.objects.create(title=catalog_data, language="ru", name="Русское имя")
    client = APIClient()
    client.cookies["anicast_lang"] = "en"
    assert client.get("/api/v1/titles/sky-test/").json()["name"] == "Sky Test"
    assert client.get("/api/v1/titles/sky-test/?lang=xx").json()["name"] == "Русское имя"


@pytest.mark.django_db
def test_genres_endpoint_localized_sorted_and_nonempty(catalog_data):
    second = Title.objects.create(name="Second Test", slug="second-test", status="finished", title_type="anime")
    second.genres.add(Genre.objects.get(slug="drama"))
    empty_genre = Genre.objects.create(name="Unused", slug="unused")
    GenreTranslation.objects.create(genre=empty_genre, language="ru", name="Неиспользуемый")
    GenreTranslation.objects.create(genre=Genre.objects.get(slug="action"), language="ru", name="Экшен")

    payload = APIClient().get("/api/v1/genres/", {"lang": "en"}).json()
    # Genres without titles are excluded entirely.
    assert [row["slug"] for row in payload] == ["drama", "action"]
    drama = payload[0]
    assert drama["name"] == "Drama"
    assert drama["titles_count"] == 2
    assert payload[1]["titles_count"] == 1

    russian = APIClient().get("/api/v1/genres/", {"lang": "ru"}).json()
    assert next(row for row in russian if row["slug"] == "action")["name"] == "Экшен"
    # Base name is the English fallback when no translation exists.
    assert next(row for row in russian if row["slug"] == "drama")["name"] == "Drama"


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
    private_origin = MediaAsset.objects.create(
        title=catalog_data,
        kind="image",
        url="https://shikimori.io/system/animes/original/1.jpg",
        thumbnail_url="https://cdn.myanimelist.net/images/anime/1.jpg",
        credit="Studio",
        rights_reference="RIGHTS-3",
        is_published=True,
    )
    response = APIClient().get("/api/v1/media/")
    assert response.status_code == 200
    assert response.json()["count"] == 2
    rows = {row["id"]: row for row in response.json()["results"]}
    assert rows[published.id]["url"] == "https://example.invalid/trailer"
    assert rows[private_origin.id]["url"] == ""
    assert rows[private_origin.id]["thumbnail_url"] == ""
    assert "shikimori" not in str(rows[private_origin.id]).lower()
    assert draft.id not in rows
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
def test_fetch_shikimori_mapping_helpers(monkeypatch):
    from catalog.management.commands import fetch_shikimori
    from catalog.management.commands.fetch_shikimori import (
        build_genre,
        build_title,
        clean_description,
        episode_count,
        map_kind,
        map_status,
    )

    monkeypatch.setattr(fetch_shikimori, "mal_poster", lambda entry: "")

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

    missing_art = build_character(role_entry, {**detail, "image": {"original": "/assets/globals/missing_original.jpg"}})
    assert missing_art["image_url"] == ""

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
def test_fetch_shikimori_poster_prefers_mal(monkeypatch):
    from catalog.management.commands import fetch_shikimori

    monkeypatch.setattr(fetch_shikimori.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        fetch_shikimori,
        "jikan_get",
        lambda path: {"data": {"images": {"jpg": {
            "large_image_url": "https://cdn.myanimelist.net/images/anime/10/47347l.jpg",
            "maximum_image_url": "https://cdn.myanimelist.net/images/anime/10/47347f.jpg",
        }}}},
    )
    entry = {"id": 16498, "name": "Shingeki no Kyojin", "image": {"original": "/system/animes/original/16498.jpg"}}
    assert fetch_shikimori.mal_poster(entry) == "https://cdn.myanimelist.net/images/anime/10/47347f.jpg"

    monkeypatch.setattr(
        fetch_shikimori,
        "jikan_get",
        lambda path: {"data": {"images": {"jpg": {"large_image_url": "https://cdn.myanimelist.net/images/anime/10/47347l.jpg"}}}},
    )
    assert fetch_shikimori.mal_poster(entry) == "https://cdn.myanimelist.net/images/anime/10/47347l.jpg"

    def broken(path):
        raise OSError("jikan down")

    monkeypatch.setattr(fetch_shikimori, "jikan_get", broken)
    assert fetch_shikimori.mal_poster(entry) == ""

    entry_missing = {"id": 1, "name": "No Art", "image": {"original": "/assets/globals/missing_original.jpg"}}
    monkeypatch.setattr(fetch_shikimori, "jikan_get", lambda path: {"data": {}})
    assert fetch_shikimori.mal_poster(entry_missing) == ""
    title = fetch_shikimori.build_title(
        entry_missing,
        {"description": "", "english": [], "japanese": [], "genres": []},
    )
    assert title["poster_url"] == ""


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
    assert link.character.image_url == ""
    assert link.character.image_origin_url.endswith("/characters/original/40882.jpg")

    payload["titles"][0]["characters"] = [{"character": "missing", "role": "supporting"}]
    with pytest.raises(Exception, match="не найден"):
        apply_payload(payload)


@pytest.mark.django_db
def test_import_catalog_preserves_local_poster_and_refreshes_private_origin():
    from catalog.management.commands.import_catalog import apply_payload

    title = Title.objects.create(
        name="Local",
        slug="10-local",
        poster_url="https://anicast.online/api/v1/media/posters/10-m-aabbccdd.jpg",
    )
    apply_payload({
        "titles": [{
            "slug": title.slug,
            "name": title.name,
            "poster_url": "https://shikimori.io/system/animes/original/10.jpg",
        }],
    })
    title.refresh_from_db()
    assert title.poster_url == "https://anicast.online/api/v1/media/posters/10-m-aabbccdd.jpg"
    assert title.poster_origin_url.endswith("/animes/original/10.jpg")


@pytest.mark.django_db
def test_import_catalog_drops_shikimori_placeholder_images():
    from catalog.management.commands.import_catalog import apply_payload

    payload = {
        "characters": [
            {
                "slug": "no-art",
                "name": "Нет арта",
                "image_url": "https://shikimori.io/assets/globals/missing_original.jpg",
                "translations": {"en": {"name": "No Art"}},
            }
        ],
        "titles": [
            {
                "slug": "no-poster",
                "name": "Без постера",
                "poster_url": "https://shikimori.io/assets/globals/missing_original.jpg?1711947446",
                "translations": {"en": {"name": "No Poster"}},
            }
        ],
    }
    apply_payload(payload)
    assert Character.objects.get(slug="no-art").image_url == ""
    assert Character.objects.get(slug="no-art").image_origin_url == ""
    assert Title.objects.get(slug="no-poster").poster_url == ""
    assert Title.objects.get(slug="no-poster").poster_origin_url == ""
