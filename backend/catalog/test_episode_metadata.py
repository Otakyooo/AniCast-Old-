from datetime import datetime, timezone as datetime_timezone
import json
from io import StringIO
from subprocess import CompletedProcess

import pytest

from catalog.episode_metadata import EpisodeMetadataError, sync_title_episode_metadata
from catalog.models import Episode, EpisodeTranslation, Title
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from library.models import EpisodeProgress


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
def test_anizip_uses_work_local_numbers_and_ignores_specials(monkeypatch):
    title = Title.objects.create(name="Season three", slug="35760-season-three")
    Episode.objects.create(title=title, number=1, name="Smoke Signal")
    payload = {"episodes": {
        "1": {"absoluteEpisodeNumber": 38, "title": {"en": "Smoke Signal"}, "airDate": "2018-07-23"},
        "2": {"absoluteEpisodeNumber": 39, "title": {"en": "Pain"}},
        "S1": {"absoluteEpisodeNumber": 40, "title": {"en": "Special"}},
    }}
    monkeypatch.setattr("catalog.episode_metadata.subprocess.run", lambda *a, **kw: CompletedProcess([], 0, json.dumps(payload)))
    result = sync_title_episode_metadata(title, fallback_first=True)
    assert result.created == 1
    assert list(title.episodes.values_list("number", flat=True)) == [1, 2]
    assert title.episodes.get(number=1).air_date.isoformat() == "2018-07-23"


@pytest.mark.django_db
def test_number_repair_is_dry_run_idempotent_and_preserves_user_progress(tmp_path):
    title = Title.objects.create(name="Season", slug="35760-season")
    target = Episode.objects.create(title=title, number=1, name="Smoke Signal")
    duplicate = Episode.objects.create(title=title, number=38, name="Smoke Signal", air_date="2018-07-23")
    EpisodeTranslation.objects.create(episode=duplicate, language="ja", name="狼煙")
    user = get_user_model().objects.create(email="numbering@example.invalid")
    progress = EpisodeProgress.objects.create(user=user, episode=target, watched_seconds=180, last_opened_at=timezone.now())
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 35760}, "episodes": {
        "1": {"absoluteEpisodeNumber": 38, "title": {"en": "Smoke Signal"}},
    }}))
    output = StringIO()
    call_command("repair_episode_numbering", title.slug, str(mapping), stdout=output)
    assert "DRY-RUN: merged=1" in output.getvalue()
    assert title.episodes.count() == 2
    target.refresh_from_db()
    assert target.air_date is None
    # A duplicate with user data is never silently deleted or reassigned.
    extra = EpisodeProgress.objects.create(user=user, episode=duplicate, last_opened_at=timezone.now())
    with pytest.raises(CommandError, match="related records"):
        call_command("repair_episode_numbering", title.slug, str(mapping), apply=True, stdout=StringIO())
    assert title.episodes.count() == 2
    extra.delete()
    call_command("repair_episode_numbering", title.slug, str(mapping), apply=True, stdout=StringIO())
    target.refresh_from_db()
    progress.refresh_from_db()
    assert title.episodes.count() == 1
    assert target.air_date.isoformat() == "2018-07-23"
    assert target.translations.get(language="ja").name == "狼煙"
    assert progress.watched_seconds == 180
    again = StringIO()
    call_command("repair_episode_numbering", title.slug, str(mapping), apply=True, stdout=again)
    assert "merged=0" in again.getvalue()


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


@pytest.mark.django_db
def test_episode_metadata_can_prefer_single_request_fallback(monkeypatch):
    title = Title.objects.create(name="Batch", slug="22-batch")
    Episode.objects.create(title=title, number=1)
    monkeypatch.setattr(
        "catalog.episode_metadata._page",
        lambda mal_id, page: pytest.fail("Jikan must not be called in fallback-first mode"),
    )
    monkeypatch.setattr("catalog.episode_metadata._anizip_rows", lambda mal_id: [{
        "mal_id": 1, "title": "Episode One", "aired": "2001-01-01",
    }])
    result = sync_title_episode_metadata(title, fallback_first=True)
    assert result.dated == 1
