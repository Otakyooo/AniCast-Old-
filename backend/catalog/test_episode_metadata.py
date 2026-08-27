from datetime import datetime, timezone as datetime_timezone

import pytest

from catalog.episode_metadata import EpisodeMetadataError, sync_title_episode_metadata
from catalog.models import Episode, EpisodeTranslation, Title


@pytest.mark.django_db
def test_episode_metadata_fills_names_dates_and_preserves_precise_or_editorial_data(monkeypatch):
    title = Title.objects.create(name="Metadata", slug="5114-metadata")
    first = Episode.objects.create(title=title, number=1)
    precise = Episode.objects.create(
        title=title,
        number=2,
        name="Редакторское название",
        air_at=datetime(2026, 8, 30, 14, 15, tzinfo=datetime_timezone.utc),
    )
    payload = {
        "data": [
            {
                "mal_id": 1,
                "title": "  Fullmetal   Alchemist\u00a0 ",
                "title_japanese": "鋼の錬金術師",
                "title_romanji": "Hagane no Renkinjutsushi",
                "aired": "2009-04-05T00:00:00+00:00",
            },
            {
                "mal_id": 2,
                "title": "The First Day",
                "title_japanese": "はじまりの日",
                "aired": "2009-04-12T00:00:00+00:00",
            },
        ],
        "pagination": {"has_next_page": False},
    }
    monkeypatch.setattr("catalog.episode_metadata.jikan_get", lambda path: payload)
    monkeypatch.setattr("catalog.episode_metadata.time.sleep", lambda seconds: None)

    result = sync_title_episode_metadata(title)
    first.refresh_from_db()
    precise.refresh_from_db()
    assert result.pages == 1
    assert result.episodes == 2
    assert result.named == 1
    assert result.dated == 1
    assert first.name == "Fullmetal Alchemist"
    assert first.air_date.isoformat() == "2009-04-05"
    assert precise.name == "Редакторское название"
    assert precise.air_at.isoformat() == "2026-08-30T14:15:00+00:00"
    assert precise.air_date.isoformat() == "2026-08-30"
    assert EpisodeTranslation.objects.get(episode=first, language="en").name == "Fullmetal Alchemist"
    assert EpisodeTranslation.objects.get(episode=first, language="ja").name == "鋼の錬金術師"


@pytest.mark.django_db
def test_episode_metadata_follows_bounded_pagination(monkeypatch):
    title = Title.objects.create(name="Paged", slug="21-paged")
    calls = []

    def page(path):
        calls.append(path)
        number = len(calls)
        return {
            "data": [{"mal_id": number, "title": f"Episode {number}", "aired": None}],
            "pagination": {"has_next_page": number == 1},
        }

    monkeypatch.setattr("catalog.episode_metadata.jikan_get", page)
    monkeypatch.setattr("catalog.episode_metadata.time.sleep", lambda seconds: None)
    result = sync_title_episode_metadata(title)
    assert result.pages == 2
    assert list(title.episodes.values_list("number", "name")) == [(1, "Episode 1"), (2, "Episode 2")]


@pytest.mark.django_db
def test_episode_metadata_falls_back_to_anizip(monkeypatch):
    title = Title.objects.create(name="Fallback", slug="21-fallback")
    Episode.objects.create(title=title, number=1)

    monkeypatch.setattr("catalog.episode_metadata._anizip_rows", lambda mal_id: [{
        "mal_id": 1,
        "title": "I'm Luffy!",
        "title_japanese": "俺はルフィ!",
        "title_russian": "Я — Луффи!",
        "aired": "1999-10-20",
    }])

    monkeypatch.setattr(
        "catalog.episode_metadata._page",
        lambda mal_id, page: (_ for _ in ()).throw(EpisodeMetadataError("timeout")),
    )
    result = sync_title_episode_metadata(title)
    episode = title.episodes.get(number=1)
    assert result.dated == 1
    assert episode.air_date.isoformat() == "1999-10-20"
    assert EpisodeTranslation.objects.get(episode=episode, language="ru").name == "Я — Луффи!"
