import struct

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from catalog import portraits
from catalog.models import Character


def png_header(width: int = 80, height: int = 120) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"


@pytest.mark.django_db
def test_portrait_api_never_exposes_private_origin_and_operator_mirror_is_local(tmp_path, monkeypatch):
    character = Character.objects.create(
        name="Local Hero",
        slug="local-hero",
        image_origin_url="https://shikimori.io/system/characters/original/40.jpg",
    )
    downloads = []

    def download(url):
        downloads.append(url)
        return png_header()

    monkeypatch.setattr("catalog.posters.download_bytes", download)
    with override_settings(POSTERS_MEDIA_ROOT=tmp_path, POSTERS_PUBLIC_BASE="https://anicast.online"):
        detail = APIClient().get("/api/v1/characters/local-hero/").json()
        assert detail["image_url"] == ""
        assert downloads == []

        portraits.mirror_record("characters", character)
        character.refresh_from_db()
        assert character.image_url.startswith("https://anicast.online/api/v1/media/posters/x-s-")
        assert downloads == [character.image_origin_url]

        local_detail = APIClient().get("/api/v1/characters/local-hero/").json()
        assert local_detail["image_url"].startswith("https://anicast.online/api/v1/media/posters/x-s-")
        local_path = local_detail["image_url"].removeprefix("https://anicast.online")
        response = APIClient().get(local_path)
        assert response.status_code == 200
        assert response["Cache-Control"] == "public, max-age=31536000, immutable"


@pytest.mark.django_db
def test_portrait_public_url_fails_closed_for_unknown_hosts():
    character = Character.objects.create(
        name="Unknown",
        slug="unknown-origin",
        image_url="https://example.invalid/portrait.jpg",
    )
    assert portraits.public_portrait_url(
        "characters", character.pk, character.image_url, character.image_origin_url
    ) == ""


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@shikimori.io/system/1.jpg",
        "https://shikimori.io:8443/system/1.jpg",
        "https://shikimori.io/system/1.jpg#fragment",
        "http://shikimori.io/system/1.jpg",
    ],
)
def test_private_origin_rejects_unsafe_url_forms(url):
    assert portraits.is_allowed_origin(url) is False


@pytest.mark.django_db
def test_new_private_origin_invalidates_generated_local_fallback():
    character = Character.objects.create(
        name="Refresh",
        slug="refresh",
        image_url="https://anicast.online/api/v1/media/posters/x-s-aabbccdd.jpg",
        image_origin_url="https://shikimori.io/system/characters/original/1.jpg",
    )
    assert portraits.set_private_origin(
        character, "https://shikimori.io/system/characters/original/2.jpg"
    ) is True
    character.refresh_from_db()
    assert character.image_url == ""
    assert character.image_origin_url.endswith("/2.jpg")
