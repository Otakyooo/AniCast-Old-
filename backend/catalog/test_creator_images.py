from catalog import creator_images, providers


def person(name, russian, image):
    return {
        "name": name,
        "russian": russian,
        "image": {"original": image},
    }


def test_creator_image_prefers_exact_original_photo(monkeypatch):
    monkeypatch.setattr(
        creator_images,
        "search_people",
        lambda name: [
            person("Someone Else", "Другой человек", "/system/people/original/2.jpg"),
            person("Tetsurou Araki", "Тэцуро Араки", "/system/people/original/5088.jpg"),
        ],
    )

    # Asserted against the configured base, not a literal domain: the provider
    # has moved hosts before, and this must follow it rather than pin it.
    assert creator_images.creator_image("Тэцуро Араки") == providers.absolute_url(
        "/system/people/original/5088.jpg"
    )


def test_creator_image_accepts_close_transliteration_but_not_missing_art(monkeypatch):
    monkeypatch.setattr(
        creator_images,
        "search_people",
        lambda name: [
            person("Shinpei Ezaki", "Симпэй Эдзаки", "/system/people/original/35807.jpg"),
        ],
    )
    assert creator_images.creator_image("Синпэй Эдзаки").endswith("/35807.jpg")

    monkeypatch.setattr(
        creator_images,
        "search_people",
        lambda name: [
            person("Unknown", "Неизвестный", "/assets/globals/missing_original.jpg"),
        ],
    )
    assert creator_images.creator_image("Совсем другой") == ""
