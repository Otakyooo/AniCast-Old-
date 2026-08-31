import pytest

from catalog.character_sync import sync_title_characters
from catalog.models import CharacterTranslation, Title


@pytest.mark.django_db
def test_character_sync_imports_full_role_list_without_detail_requests(monkeypatch):
    title = Title.objects.create(name="One", slug="21-one")
    monkeypatch.setattr("catalog.character_sync._character_roles", lambda anime_id: [
        {"rolesEn": ["Main"], "character": {"id": "40", "name": "Luffy", "russian": "Луффи", "poster": {
            "originalUrl": "https://shikimori.io/uploads/poster/characters/40/original.jpeg",
        }}},
        {"rolesEn": ["Supporting"], "character": {"id": "723", "name": "Nami", "russian": "Нами"}},
    ])

    result = sync_title_characters(title)
    assert result.discovered == 2
    assert title.character_links.count() == 2
    assert list(title.character_links.values_list("role", flat=True)) == ["protagonist", "supporting"]
    luffy = title.characters.get(slug="40-luffy")
    assert luffy.image_url == ""
    assert luffy.image_origin_url.endswith("/characters/40/original.jpeg")
    assert CharacterTranslation.objects.get(character=luffy, language="ru").name == "Луффи"
