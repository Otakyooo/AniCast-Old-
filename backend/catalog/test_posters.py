import hashlib
import os
import struct
import time
import zlib

import pytest
from django.test import Client, override_settings
from django.core.management import call_command

from catalog import posters
from catalog.models import Title


def png_bytes(width: int, height: int) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x40\x50\x60" * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def jpeg_probe_bytes(width: int, height: int) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xc0"
        + struct.pack(">H", 11)
        + bytes([8])
        + struct.pack(">HH", height, width)
        + bytes([1])
        + b"\x01\x11\x00"
        + b"\xff\xd9"
    )


@pytest.fixture
def poster_media_root(tmp_path):
    with override_settings(POSTERS_MEDIA_ROOT=tmp_path / "posters", POSTERS_PUBLIC_BASE="https://cdn.test"):
        yield tmp_path / "posters"


def test_image_dimensions_parses_png_and_jpeg():
    assert posters.image_dimensions(png_bytes(300, 446)) == ("png", 300, 446)
    assert posters.image_dimensions(jpeg_probe_bytes(420, 600)) == ("jpg", 420, 600)
    with pytest.raises(ValueError):
        posters.image_dimensions(b"<html>not an image</html>")


def test_poster_tier_parsing():
    url = "https://cdn.test/api/v1/media/posters/21-m-ab12cd34.png"
    assert posters.current_tier(url) == "m"
    assert posters.current_tier("https://shikimori.one/system/animes/original/21.jpg") is None


def test_is_allowed_poster_url():
    assert posters.is_allowed_poster_url("https://cdn.myanimelist.net/images/anime/1.jpg")
    assert posters.is_allowed_poster_url("https://shikimori.io/system/animes/original/5.jpg")
    assert not posters.is_allowed_poster_url("http://cdn.myanimelist.net/images/anime/1.jpg")
    assert not posters.is_allowed_poster_url("https://evil.example.net/images/anime/1.jpg")


@pytest.mark.django_db
def test_refresh_upgrades_to_local_maximum_artwork(poster_media_root, monkeypatch):
    title = Title.objects.create(
        name="Low", slug="21-low",
        poster_url="https://shikimori.io/system/animes/original/21.jpg",
    )
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: ("https://cdn.myanimelist.net/images/anime/21.jpg", "m"))
    monkeypatch.setattr(posters, "download_bytes", lambda url: png_bytes(400, 600))

    result = posters.refresh_title(title, apply_changes=True)
    assert result[0] == "maximum"
    title.refresh_from_db()
    assert title.poster_url.startswith("https://cdn.test/api/v1/media/posters/21-m-")
    filename = title.poster_url.rsplit("/", 1)[-1]
    assert (poster_media_root / filename).is_file()


@pytest.mark.django_db
def test_refresh_mirrors_fallback_when_jikan_down(poster_media_root, monkeypatch):
    shikimori = "https://shikimori.one/system/animes/original/1735.jpg"
    title = Title.objects.create(name="Down", slug="1735-down", poster_url=shikimori)
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: None)
    monkeypatch.setattr(posters, "download_bytes", lambda url: png_bytes(225, 318))

    result, _ = posters.refresh_title(title, apply_changes=True)
    assert result == "mirrored"
    title.refresh_from_db()
    assert "-s-" in title.poster_url and title.poster_url.startswith("https://cdn.test/api/")


@pytest.mark.django_db
def test_refresh_keeps_large_when_maximum_absent(poster_media_root, monkeypatch):
    poster_media_root.mkdir(parents=True, exist_ok=True)
    fallback_url = posters.public_poster_url("21-s-11111111.png")
    (poster_media_root / "21-s-11111111.png").write_bytes(png_bytes(225, 318))
    title = Title.objects.create(name="Large", slug="21-large", poster_url=fallback_url)
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: ("https://cdn.myanimelist.net/images/anime/21l.jpg", "l"))
    monkeypatch.setattr(posters, "download_bytes", lambda url: png_bytes(300, 446))

    result, _ = posters.refresh_title(title, apply_changes=True)
    assert result == "large"
    title.refresh_from_db()
    assert "-l-" in title.poster_url
    assert not (poster_media_root / "21-s-11111111.png").exists()

    again, _ = posters.refresh_title(title, apply_changes=True)
    assert again == "current"


@pytest.mark.django_db
def test_batch_skips_titles_at_maximum_tier(poster_media_root, monkeypatch):
    data = png_bytes(400, 600)
    filename = posters.store_poster(30, "m", data)
    Title.objects.create(name="Max", slug="30-max", poster_url=posters.public_poster_url(filename))

    calls: list[int] = []

    def probe(mal_id):
        calls.append(mal_id)
        return None

    monkeypatch.setattr(posters, "mal_artwork_with_tier", probe)
    outcomes = posters.refresh_batch(limit=10, apply_changes=False)
    assert calls == []
    assert outcomes == []


@pytest.mark.django_db
def test_refresh_deadline_stops_new_work(poster_media_root, monkeypatch):
    for index in range(3):
        Title.objects.create(name=f"Slow {index}", slug=f"{70 + index}-slow",
                             poster_url="https://shikimori.one/system/animes/original/70.jpg")
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: None)
    monkeypatch.setattr(posters, "download_bytes", lambda url: png_bytes(225, 318))

    outcomes = posters.refresh_batch(limit=0, apply_changes=True, deadline=time.monotonic() - 1)
    assert outcomes == []


@pytest.mark.django_db
def test_invalid_download_labels_rejected_content(poster_media_root, monkeypatch):
    original = "https://shikimori.io/system/animes/original/99.jpg"
    title = Title.objects.create(name="Bad", slug="99-bad", poster_url=original)
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: ("https://cdn.myanimelist.net/images/anime/99.jpg", "m"))
    monkeypatch.setattr(posters, "download_bytes", lambda url: b"garbage")

    result, _ = posters.refresh_title(title, apply_changes=True)
    assert result == "invalid"
    title.refresh_from_db()
    assert title.poster_url == original


@pytest.mark.django_db
def test_network_failure_still_labeled_error(poster_media_root, monkeypatch):
    title = Title.objects.create(name="Net", slug="net-title", poster_url="https://shikimori.one/system/animes/original/98.jpg")
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: None)
    monkeypatch.setattr(posters, "download_bytes", lambda url: (_ for _ in ()).throw(OSError("timeout")))

    result, _ = posters.refresh_title(title, apply_changes=True)
    assert result == "error"
    title.refresh_from_db()
    assert title.poster_url == "https://shikimori.one/system/animes/original/98.jpg"


def test_digest_collision_rejects_different_content(poster_media_root):
    data = png_bytes(300, 446)
    digest = hashlib.sha256(data).hexdigest()[:posters.DIGEST_HEX_CHARS]
    conflicting = posters.ensure_media_dir() / f"60-m-{digest}.png"
    conflicting.write_bytes(png_bytes(301, 447))

    with pytest.raises(ValueError, match="collision"):
        posters.store_poster(60, "m", data)
    assert conflicting.read_bytes() == png_bytes(301, 447)


def test_long_digest_names_parse_and_serve(poster_media_root):
    data = png_bytes(240, 360)
    filename = posters.store_poster(61, "l", data)
    assert len(filename.rsplit("-", 1)[-1].split(".")[0]) == posters.DIGEST_HEX_CHARS
    assert posters.current_tier(posters.public_poster_url(filename)) == "l"
    assert posters.POSTER_NAME_RE.match("21-s-ab12cd34.jpg")
    assert not posters.POSTER_NAME_RE.match("21-s-ab1.jpg")


@pytest.mark.django_db
def test_adopt_records_remote_origin(poster_media_root, monkeypatch):
    shikimori = "https://shikimori.one/system/animes/original/31.jpg"
    title = Title.objects.create(name="Origin", slug="31-origin", poster_url=shikimori)
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: ("https://cdn.myanimelist.net/images/anime/31.jpg", "m"))
    monkeypatch.setattr(posters, "download_bytes", lambda url: png_bytes(400, 600))

    posters.refresh_title(title, apply_changes=True)
    title.refresh_from_db()
    assert title.poster_origin_url == shikimori

    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: None)
    (poster_media_root / title.poster_url.rsplit("/", 1)[-1]).unlink()
    result, _ = posters.refresh_title(title, apply_changes=True)
    title.refresh_from_db()
    assert result == "mirrored"
    assert "-s-" in title.poster_url
    assert title.poster_origin_url == shikimori


@pytest.mark.django_db
def test_missing_local_file_becomes_candidate_again(poster_media_root, monkeypatch):
    local_url = posters.public_poster_url("40-m-cafecafe.png")
    Title.objects.create(name="Ghost", slug="40-ghost", poster_url=local_url)

    assert posters.stored_tier(local_url) is None
    calls: list[int] = []

    def probe(mal_id):
        calls.append(mal_id)
        return None

    monkeypatch.setattr(posters, "mal_artwork_with_tier", probe)
    outcomes = posters.refresh_batch(limit=5, apply_changes=False)
    assert calls == [40]
    assert outcomes[0][0] == "unavailable"


@pytest.mark.django_db
def test_restore_origins_reverts_local_urls(poster_media_root, monkeypatch):
    origin = "https://shikimori.io/system/animes/original/50.jpg"
    title = Title.objects.create(
        name="Revert", slug="50-revert",
        poster_url=posters.public_poster_url("50-s-aabbccdd.jpg"),
        poster_origin_url=origin,
    )
    remote = Title.objects.create(name="Remote", slug="51-remote", poster_url=origin)

    call_command("backfill_posters", "--restore-origins")
    title.refresh_from_db()
    remote.refresh_from_db()
    assert "-s-" in title.poster_url

    call_command("backfill_posters", "--restore-origins", "--apply")
    title.refresh_from_db()
    assert title.poster_url == origin


def test_download_rejects_redirect_escape(monkeypatch):
    def fake_hop(url):
        return 302, b"", "http://169.254.169.254/latest/meta-data/"

    monkeypatch.setattr(posters, "_fetch_hop", fake_hop)
    with pytest.raises(ValueError, match="not allowed"):
        posters.download_bytes("https://cdn.myanimelist.net/images/anime/1.jpg")


def test_download_follows_allowlisted_redirects(monkeypatch):
    hops = {
        "https://shikimori.io/a.jpg": (302, b"", "https://shikimori.one/b.jpg"),
        "https://shikimori.one/b.jpg": (200, b"\xff\xd8\xff\xe0data", ""),
    }

    def fake_hop(url):
        return hops[url]

    monkeypatch.setattr(posters, "_fetch_hop", fake_hop)
    data = posters.download_bytes("https://shikimori.io/a.jpg")
    assert data == b"\xff\xd8\xff\xe0data"


def test_sweep_part_files_removes_stale_only(poster_media_root):
    poster_media_root.mkdir(parents=True, exist_ok=True)
    stale = poster_media_root / "1-m-00000000.jpg.part"
    fresh = poster_media_root / "2-m-11111111.jpg.part"
    stale.write_bytes(b"x")
    fresh.write_bytes(b"y")
    old = time.time() - posters.PART_FILE_MAX_AGE_SECONDS - 10
    os.utime(stale, (old, old))

    removed = posters.sweep_part_files()
    assert removed == 1
    assert not stale.exists() and fresh.exists()


@pytest.mark.django_db
def test_dry_run_writes_nothing(poster_media_root, monkeypatch, capsys):
    title = Title.objects.create(
        name="Plan", slug="7-plan",
        poster_url="https://shikimori.one/system/animes/original/7.jpg",
    )
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: ("https://cdn.myanimelist.net/images/anime/7.jpg", "m"))

    call_command("backfill_posters")
    out = capsys.readouterr().out
    assert "plan" in out
    title.refresh_from_db()
    assert "shikimori" in title.poster_url
    assert list(poster_media_root.glob("*")) == []


@pytest.mark.django_db
def test_command_applies_and_reports_summary(poster_media_root, monkeypatch, capsys):
    title = Title.objects.create(
        name="Apply", slug="8-apply",
        poster_url="https://shikimori.one/system/animes/original/8.jpg",
    )
    monkeypatch.setattr(posters, "mal_artwork_with_tier", lambda mal_id: ("https://cdn.myanimelist.net/images/anime/8.jpg", "m"))
    monkeypatch.setattr(posters, "download_bytes", lambda url: jpeg_probe_bytes(420, 600))

    call_command("backfill_posters", "--apply")
    out = capsys.readouterr().out
    assert "applied:" in out and "maximum: 1" in out
    title.refresh_from_db()
    assert title.poster_url.endswith(".jpg")


def test_poster_media_view_serves_immutable_file(poster_media_root):
    data = png_bytes(200, 280)
    filename = posters.store_poster(55, "s", data)
    client = Client()
    response = client.get(f"/api/v1/media/posters/{filename}")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["Cache-Control"] == "public, max-age=31536000, immutable"
    assert b"".join(response.streaming_content) == data
    assert client.get("/api/v1/media/posters/../secret.png").status_code == 404
    assert client.get("/api/v1/media/posters/not-a-poster.txt").status_code == 404
