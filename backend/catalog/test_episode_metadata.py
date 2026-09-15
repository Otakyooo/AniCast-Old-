from datetime import datetime, timezone as datetime_timezone
import json
from io import StringIO
from subprocess import CompletedProcess

import pytest

from catalog.episode_metadata import EpisodeMetadataError, sync_title_episode_metadata
from catalog.models import Episode, EpisodeTranslation, Source, Title
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
def test_anizip_uses_work_local_numbers_and_files_specials_in_season_zero(monkeypatch):
    """The work-local key numbers the run; an S key is a special, not episode 1.

    A special may carry the same number as a regular episode, which is why the
    season is part of the key rather than a label.
    """
    title = Title.objects.create(name="Season three", slug="35760-season-three")
    Episode.objects.create(title=title, number=1, name="Smoke Signal")
    payload = {"episodes": {
        "1": {"absoluteEpisodeNumber": 38, "title": {"en": "Smoke Signal"}, "airDate": "2018-07-23"},
        "2": {"absoluteEpisodeNumber": 39, "title": {"en": "Pain"}},
        "S1": {"absoluteEpisodeNumber": 40, "title": {"en": "Special", "ja": "スペシャル"}},
    }}
    monkeypatch.setattr("catalog.episode_metadata.subprocess.run", lambda *a, **kw: CompletedProcess([], 0, json.dumps(payload)))
    result = sync_title_episode_metadata(title, fallback_first=True)
    assert result.created == 2
    assert list(title.episodes.filter(season_number=1).values_list("number", flat=True)) == [1, 2]
    assert title.episodes.get(number=1, season_number=1).air_date.isoformat() == "2018-07-23"
    special = title.episodes.get(season_number=0)
    assert (special.number, special.name) == (1, "Special")
    assert EpisodeTranslation.objects.get(episode=special, language="ja").name == "スペシャル"


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

    monkeypatch.setattr("catalog.episode_metadata._anizip_rows", lambda mal_id: ([{
        "mal_id": 1,
        "title": "I'm Luffy!",
        "title_japanese": "俺はルフィ!",
        "title_russian": "Я — Луффи!",
        "aired": "1999-10-20",
    }], []))

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
    monkeypatch.setattr("catalog.episode_metadata._anizip_rows", lambda mal_id: ([{
        "mal_id": 1, "title": "Episode One", "aired": "2001-01-01",
    }], []))
    result = sync_title_episode_metadata(title, fallback_first=True)
    assert result.dated == 1


@pytest.mark.django_db
def test_prune_deletes_artifact_rows_and_rescues_the_local_max_name(tmp_path):
    """Rows above the local run are the shifted import's copies, not episodes.

    Local 1..3 mapped to absolute 4..6: rows 1..2 are correct, row 3 carries
    local 1's name because the import wrote local 1..3 as absolute 4..6, and rows
    4..6 hold local 1..3's names. Local 3's own name therefore lives on row 6 and
    must be copied down before the rows above are deleted.
    """
    title = Title.objects.create(name="Shifted", slug="100-shifted")
    Episode.objects.create(title=title, number=1, name="Alpha")
    Episode.objects.create(title=title, number=2, name="Beta")
    Episode.objects.create(title=title, number=3, name="Alpha")
    Episode.objects.create(title=title, number=4, name="Alpha")
    Episode.objects.create(title=title, number=5, name="Beta")
    Episode.objects.create(title=title, number=6, name="Gamma")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 100}, "episodes": {
        "1": {"absoluteEpisodeNumber": 4, "title": {"en": "Alpha"}},
        "2": {"absoluteEpisodeNumber": 5, "title": {"en": "Beta"}},
        "3": {"absoluteEpisodeNumber": 6, "title": {"en": "Gamma"}},
    }}))
    output = StringIO()
    call_command("prune_episode_artifacts", title.slug, str(mapping), apply=True, stdout=output)
    assert "APPLIED: repaired=3 kept=0" in output.getvalue()
    assert list(title.episodes.order_by("number").values_list("number", "name")) == [
        (1, "Alpha"),
        (2, "Beta"),
        (3, "Gamma"),
    ]


@pytest.mark.django_db
def test_prune_dry_run_deletes_nothing(tmp_path):
    title = Title.objects.create(name="Shifted", slug="100-shifted")
    for number, name in ((1, "Alpha"), (2, "Beta"), (3, "Alpha"), (4, "Alpha")):
        Episode.objects.create(title=title, number=number, name=name)
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 100}, "episodes": {
        "1": {"absoluteEpisodeNumber": 3, "title": {"en": "Alpha"}},
        "2": {"absoluteEpisodeNumber": 4, "title": {"en": "Beta"}},
    }}))
    output = StringIO()
    call_command("prune_episode_artifacts", title.slug, str(mapping), stdout=output)
    assert "DRY-RUN: repaired=2 kept=0" in output.getvalue()
    assert title.episodes.count() == 4


@pytest.mark.django_db
def test_prune_moves_players_onto_the_row_it_duplicates(tmp_path):
    """The artifact's player links outlive the row that held them."""
    title = Title.objects.create(name="Sourced", slug="200-sourced")
    Episode.objects.create(title=title, number=1, name="Alpha")
    Episode.objects.create(title=title, number=2, name="Beta")
    artifact = Episode.objects.create(title=title, number=3, name="Alpha")
    Source.objects.create(
        episode=artifact, name="Kodik · AniDUB", url="https://kodikplayer.com/seria/1/x/720p"
    )
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 200}, "episodes": {
        "1": {"absoluteEpisodeNumber": 3, "title": {"en": "Alpha"}},
        "2": {"absoluteEpisodeNumber": 4, "title": {"en": "Beta"}},
    }}))
    output = StringIO()
    call_command("prune_episode_artifacts", title.slug, str(mapping), apply=True, stdout=output)
    assert "repaired=1 kept=0" in output.getvalue()
    assert list(title.episodes.order_by("number").values_list("number", flat=True)) == [1, 2]
    moved = Source.objects.get(url="https://kodikplayer.com/seria/1/x/720p")
    assert moved.episode.number == 1


@pytest.mark.django_db
def test_prune_moves_only_the_players_the_target_lacks(tmp_path):
    """A URL the target already offers is not added twice."""
    title = Title.objects.create(name="Overlap", slug="250-overlap")
    canonical = Episode.objects.create(title=title, number=1, name="Alpha")
    Episode.objects.create(title=title, number=2, name="Beta")
    artifact = Episode.objects.create(title=title, number=3, name="Alpha")
    shared = "https://kodikplayer.com/seria/1/shared/720p"
    Source.objects.create(episode=canonical, name="Kodik · A", url=shared)
    Source.objects.create(episode=artifact, name="Kodik · A", url=shared)
    Source.objects.create(episode=artifact, name="Kodik · B", url="https://kodikplayer.com/seria/9/b/720p")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 250}, "episodes": {
        "1": {"absoluteEpisodeNumber": 3, "title": {"en": "Alpha"}},
        "2": {"absoluteEpisodeNumber": 4, "title": {"en": "Beta"}},
    }}))
    call_command("prune_episode_artifacts", title.slug, str(mapping), apply=True, stdout=StringIO())
    assert sorted(Source.objects.filter(episode=canonical).values_list("url", flat=True)) == sorted(
        [shared, "https://kodikplayer.com/seria/9/b/720p"]
    )
    assert Source.objects.count() == 2


@pytest.mark.django_db
def test_prune_refuses_a_title_holding_a_possible_special(tmp_path):
    """A row named something the local run does not know may be a genuine special.

    One Punch Man's rows 13..18 are its six OVAs and two of them kept their own
    titles, so nothing in that title can be treated as a shifted copy.
    """
    title = Title.objects.create(name="Special", slug="300-special")
    Episode.objects.create(title=title, number=1, name="Alpha")
    Episode.objects.create(title=title, number=2, name="Recap Special")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 300}, "episodes": {
        "1": {"absoluteEpisodeNumber": 2, "title": {"en": "Alpha"}},
    }}))
    with pytest.raises(CommandError, match="may be genuine specials"):
        call_command("prune_episode_artifacts", title.slug, str(mapping), apply=True, stdout=StringIO())
    assert title.episodes.count() == 2


@pytest.mark.django_db
def test_prune_keeps_a_row_carrying_user_data(tmp_path):
    """Progress is someone's data and is not this command's to move."""
    title = Title.objects.create(name="Watched", slug="500-watched")
    Episode.objects.create(title=title, number=1, name="Alpha")
    Episode.objects.create(title=title, number=2, name="Beta")
    artifact = Episode.objects.create(title=title, number=3, name="Alpha")
    user = get_user_model().objects.create_user(email="watcher@example.com", password="A-strong-passphrase-2042")
    EpisodeProgress.objects.create(user=user, episode=artifact, last_opened_at=timezone.now())
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 500}, "episodes": {
        "1": {"absoluteEpisodeNumber": 3, "title": {"en": "Alpha"}},
        "2": {"absoluteEpisodeNumber": 4, "title": {"en": "Beta"}},
    }}))
    output = StringIO()
    call_command("prune_episode_artifacts", title.slug, str(mapping), apply=True, stdout=output)
    assert "repaired=0 kept=1" in output.getvalue()
    assert title.episodes.count() == 3

def _kodik(specials: dict[str, str]):
    """A Kodik search result whose season zero maps a pack id to a special number."""
    from catalog.kodik import KodikSearchResult

    return KodikSearchResult(total=1, results=[
        {"seasons": {0: {"episodes": {
            number: {"link": f"//kodikplayer.com/seria/{pack}/x/720p"}
            for number, pack in specials.items()
        }}}},
    ])


@pytest.mark.django_db
def test_name_repair_leaves_text_the_provider_never_supplied(tmp_path):
    """Spelling drift is not a misplaced copy, so it is reported and skipped."""
    title = Title.objects.create(name="Brotherhood", slug="5114-brotherhood")
    Episode.objects.create(title=title, number=1, name="Envoy From the East")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 5114}, "episodes": {
        "1": {"title": {"en": "The Envoy from the East"}},
    }}))
    output = StringIO()
    call_command("repair_episode_names", title.slug, str(mapping), apply=True, stdout=output)
    assert "renamed=0" in output.getvalue()
    assert "is not a provider title" in output.getvalue()
    assert Episode.objects.get(title=title, number=1).name == "Envoy From the East"


@pytest.mark.django_db
def test_name_repair_fixes_the_rest_when_one_row_is_unexplained(tmp_path):
    """Rows are independent: one unexplained name no longer blocks the others."""
    title = Title.objects.create(name="Shippuuden", slug="1735-shippuuden")
    Episode.objects.create(title=title, number=1, name="Something We Did Not Write")
    Episode.objects.create(title=title, number=2, name="Gamma")
    Episode.objects.create(title=title, number=3, name="Gamma")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 1735}, "episodes": {
        "1": {"title": {"en": "Alpha"}},
        "2": {"title": {"en": "Beta"}},
        "3": {"title": {"en": "Gamma"}},
    }}))
    output = StringIO()
    call_command("repair_episode_names", title.slug, str(mapping), apply=True, stdout=output)
    assert "renamed=1" in output.getvalue()
    assert Episode.objects.get(title=title, number=1).name == "Something We Did Not Write"
    assert Episode.objects.get(title=title, number=2).name == "Beta"
    assert Episode.objects.get(title=title, number=3).name == "Gamma"

def _kodik_season_zero(specials: dict[str, str]):
    """A Kodik search result whose season zero maps a pack id to a special number."""
    from catalog.kodik import KodikSearchResult

    return KodikSearchResult(total=1, results=[
        {"seasons": {0: {"episodes": {
            number: {"link": f"//kodikplayer.com/seria/{pack}/x/720p"}
            for number, pack in specials.items()
        }}}},
    ])


@pytest.mark.django_db
def test_specials_repair_relocates_a_legacy_row_onto_its_special(tmp_path, monkeypatch):
    """The row the old import left at 13 is special 1, so its players move to S1.

    Renaming it in place would put special 1's title on special 13's players.
    """
    title = Title.objects.create(name="Punch", slug="30276-punch")
    Episode.objects.create(title=title, number=1, name="The Strongest Man")
    first = Episode.objects.create(title=title, number=13, name="Unyielding Justice")
    anchor = Episode.objects.create(title=title, number=18, name="The Far Too Impossible Case of Murder")
    Source.objects.create(episode=first, name="Kodik · A", url="https://kodikplayer.com/seria/852617/a/720p")
    Source.objects.create(episode=anchor, name="Kodik · A", url="https://kodikplayer.com/seria/852622/f/720p")
    monkeypatch.setattr(
        "catalog.management.commands.repair_episode_specials.search_by_shikimori",
        lambda mal_id, **kwargs: _kodik_season_zero({"1": "852617", "6": "852622"}),
    )
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 30276}, "episodes": {
        "1": {"title": {"en": "The Strongest Man"}},
        "S1": {"title": {"en": "The Shadow That Snuck Up Too Close"}},
        "S6": {"title": {"en": "The Far Too Impossible Case of Murder"}},
    }}))
    output = StringIO()
    call_command("repair_episode_specials", title.slug, str(mapping), apply=True, stdout=output)
    assert "relocated=2" in output.getvalue()
    # Special 1 now holds the player, and the legacy row is gone.
    assert not Episode.objects.filter(title=title, season_number=1, number=13).exists()
    moved = Source.objects.get(url="https://kodikplayer.com/seria/852617/a/720p")
    assert (moved.episode.season_number, moved.episode.number) == (0, 1)
    # The regular run is untouched.
    assert Episode.objects.get(title=title, season_number=1, number=1).name == "The Strongest Man"


@pytest.mark.django_db
def test_specials_repair_handles_a_shifted_special_numbering(tmp_path, monkeypatch):
    """Brotherhood's four OVAs are S2..S5, because its S1 is a recap."""
    title = Title.objects.create(name="Brotherhood", slug="5114-brotherhood")
    Episode.objects.create(title=title, number=64, name="Journey`s End")
    legacy = Episode.objects.create(title=title, number=65, name="A Fierce Counterattack")
    anchor = Episode.objects.create(title=title, number=68, name="Yet Another Man`s Battlefield")
    Source.objects.create(episode=legacy, name="Kodik · A", url="https://kodikplayer.com/seria/514003/a/720p")
    Source.objects.create(episode=anchor, name="Kodik · B", url="https://kodikplayer.com/seria/786499/b/720p")
    monkeypatch.setattr(
        "catalog.management.commands.repair_episode_specials.search_by_shikimori",
        lambda mal_id, **kwargs: _kodik_season_zero({"1": "514003", "4": "786499"}),
    )
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 5114}, "episodes": {
        "64": {"title": {"en": "Journey`s End"}},
        "S1": {"title": {"en": '"Hagane no Renkinjutsushi" Complete Clarification!!'}},
        "S2": {"title": {"en": "The Blind Alchemist"}},
        "S5": {"title": {"en": "Yet Another Man`s Battlefield"}},
    }}))
    output = StringIO()
    call_command("repair_episode_specials", title.slug, str(mapping), apply=True, stdout=output)
    assert "offset +1" in output.getvalue()
    moved = Source.objects.get(url="https://kodikplayer.com/seria/514003/a/720p")
    assert (moved.episode.season_number, moved.episode.number) == (0, 2)
    assert not Episode.objects.filter(title=title, number=65).exists()


@pytest.mark.django_db
def test_specials_repair_leaves_a_row_whose_season_zero_packs_disagree(tmp_path, monkeypatch):
    """Two season-zero packs naming different specials identify nothing."""
    title = Title.objects.create(name="Punch", slug="30276-punch")
    row = Episode.objects.create(title=title, number=13, name="Unyielding Justice")
    Source.objects.create(episode=row, name="Kodik · A", url="https://kodikplayer.com/seria/852617/a/720p")
    Source.objects.create(episode=row, name="Kodik · B", url="https://kodikplayer.com/seria/852622/f/720p")
    monkeypatch.setattr(
        "catalog.management.commands.repair_episode_specials.search_by_shikimori",
        lambda mal_id, **kwargs: _kodik_season_zero({"1": "852617", "6": "852622"}),
    )
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"mappings": {"mal_id": 30276}, "episodes": {
        "S1": {"title": {"en": "The Shadow That Snuck Up Too Close"}},
        "S6": {"title": {"en": "The Far Too Impossible Case of Murder"}},
    }}))
    output = StringIO()
    call_command("repair_episode_specials", title.slug, str(mapping), apply=True, stdout=output)
    assert "relocated=0" in output.getvalue()
    assert Episode.objects.filter(title=title, number=13).exists()
