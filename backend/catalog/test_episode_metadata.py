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
def test_number_repair_ignores_a_shift_that_only_looks_self_overlapping(tmp_path):
    """A season shifted by its own length is not a real overlap.

    Noragami Aragoto maps local 1..13 to absolute 13..25, so 13 reads as both a
    target and a source on paper. The catalog only holds rows up to 24, so the
    pair needing row 25 does nothing and the rest are unambiguous.
    """
    title = Title.objects.create(name="Aragoto", slug="30503-aragoto")
    Episode.objects.create(title=title, number=1, name="Bearing a Posthumous Name", air_date="2015-10-03")
    Episode.objects.create(title=title, number=13, name="Bearing a Posthumous Name", air_date="2015-10-03")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 30503}, "episodes": {
        "1": {"absoluteEpisodeNumber": 13, "title": {"en": "Bearing a Posthumous Name"}},
        "13": {"absoluteEpisodeNumber": 25, "title": {"en": "The God of Fortune`s Message"}},
    }}))
    output = StringIO()
    call_command("repair_episode_numbering", title.slug, str(mapping), apply=True, stdout=output)
    assert "APPLIED: merged=1" in output.getvalue()
    assert list(title.episodes.values_list("number", flat=True)) == [1]


@pytest.mark.django_db
def test_number_repair_refuses_a_genuine_chain(tmp_path):
    """When the whole chain is present, one number is both source and target."""
    title = Title.objects.create(name="Chain", slug="1-chain")
    for number in (1, 13, 25):
        Episode.objects.create(title=title, number=number, name="Same Name", air_date="2018-01-01")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 1}, "episodes": {
        "1": {"absoluteEpisodeNumber": 13, "title": {"en": "Same Name"}},
        "13": {"absoluteEpisodeNumber": 25, "title": {"en": "Same Name"}},
    }}))
    with pytest.raises(CommandError, match="Overlapping number ranges"):
        call_command("repair_episode_numbering", title.slug, str(mapping), apply=True, stdout=StringIO())
    assert title.episodes.count() == 3


@pytest.mark.django_db
def test_number_repair_accepts_provider_spelling_drift_when_dates_agree(tmp_path):
    """Jikan and ani.zip capitalise and punctuate the same episode differently."""
    title = Title.objects.create(name="Season three", slug="36456-season-three")
    Episode.objects.create(title=title, number=5, name="Drive it Home, Iron Fist!!!", air_date="2018-05-05")
    Episode.objects.create(title=title, number=43, name="Drive It Home, Iron Fist!!!", air_date="2018-05-05")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 36456}, "episodes": {
        "5": {"absoluteEpisodeNumber": 43, "title": {"en": "Drive It Home, Iron Fist!!!"}},
    }}))
    output = StringIO()
    call_command("repair_episode_numbering", title.slug, str(mapping), apply=True, stdout=output)
    assert "APPLIED: merged=1" in output.getvalue()
    assert list(title.episodes.values_list("number", flat=True)) == [5]


@pytest.mark.django_db
def test_number_repair_still_refuses_a_fuzzy_name_with_a_different_date(tmp_path):
    """A normalized name alone must never confirm an identity."""
    title = Title.objects.create(name="Season three", slug="36456-season-three-b")
    Episode.objects.create(title=title, number=5, name="Drive it Home, Iron Fist!!!", air_date="2018-05-05")
    Episode.objects.create(title=title, number=43, name="Drive It Home, Iron Fist!!!", air_date="2018-05-12")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 36456}, "episodes": {
        "5": {"absoluteEpisodeNumber": 43, "title": {"en": "Drive It Home, Iron Fist!!!"}},
    }}))
    with pytest.raises(CommandError, match="Unconfirmed identity"):
        call_command("repair_episode_numbering", title.slug, str(mapping), apply=True, stdout=StringIO())
    assert title.episodes.count() == 2


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
