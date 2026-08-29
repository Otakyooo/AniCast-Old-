from catalog.management.commands.sync_title_staff import select_staff


def entry(person_id, name, roles_en, roles_ru):
    return {
        "rolesEn": roles_en,
        "rolesRu": roles_ru,
        "person": {"id": person_id, "name": name, "russian": "", "poster": {}},
    }


def test_select_staff_uses_exact_roles_and_creative_priority():
    staff = select_staff([
        entry(1, "Episode Person", ["Episode Director"], ["Режиссёр эпизодов"]),
        entry(2, "Author", ["Original Creator"], ["Автор оригинала"]),
        entry(3, "Series Director", ["Director", "Storyboard"], ["Режиссёр", "Раскадровка"]),
        entry(4, "Voice Actor", ["Japanese"], ["Сэйю"]),
    ])
    assert [item.name for item in staff] == ["Author", "Series Director", "Episode Person"]
    assert staff[1].role_ru == "Режиссёр · Раскадровка"
    assert staff[2].role == "episode_director"
