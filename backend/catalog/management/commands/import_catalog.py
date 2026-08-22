import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from catalog.models import (
    LANGUAGE_CHOICES,
    Character,
    CharacterTranslation,
    Episode,
    EpisodeTranslation,
    Franchise,
    FranchiseTranslation,
    Genre,
    GenreTranslation,
    Provider,
    Source,
    Title,
    TitleCharacter,
    TitleTranslation,
)
from catalog.playback import source_url_allowed, validate_provider_configuration

SUPPORTED_LANGUAGES = {code for code, _ in LANGUAGE_CHOICES}


def require_string(value, path):
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"{path}: ожидается непустая строка")
    return value.strip()


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise CommandError("Корень JSON должен быть объектом")
    for section in ["genres", "franchises", "characters", "providers", "titles"]:
        if not isinstance(payload.get(section, []), list):
            raise CommandError(f"{section}: ожидается массив")
        for index, item in enumerate(payload.get(section, [])):
            if not isinstance(item, dict):
                raise CommandError(f"{section}[{index}]: ожидается объект")
            require_string(item.get("slug"), f"{section}[{index}].slug")
            require_string(item.get("name"), f"{section}[{index}].name")
            validate_translations(item.get("translations", {}), f"{section}[{index}].translations")
            if section == "providers":
                try:
                    validate_provider_configuration(
                        item.get("playback_adapter"),
                        item.get("playback_config", {}),
                        item.get("allowed_hosts", []),
                    )
                except ValueError as error:
                    raise CommandError(f"providers[{index}]: {error}") from error
    title_slugs = set()
    for index, item in enumerate(payload.get("titles", [])):
        if not isinstance(item, dict):
            raise CommandError(f"titles[{index}]: ожидается объект")
        slug = require_string(item.get("slug"), f"titles[{index}].slug")
        require_string(item.get("name"), f"titles[{index}].name")
        if not isinstance(item.get("genres", []), list):
            raise CommandError(f"titles[{index}].genres: ожидается массив slug")
        if slug in title_slugs:
            raise CommandError(f"titles[{index}].slug: дубликат {slug}")
        title_slugs.add(slug)
        character_links = item.get("characters", [])
        if not isinstance(character_links, list):
            raise CommandError(f"titles[{index}].characters: ожидается массив")
        linked_characters = set()
        for link_index, link in enumerate(character_links):
            prefix = f"titles[{index}].characters[{link_index}]"
            if not isinstance(link, dict):
                raise CommandError(f"{prefix}: ожидается объект")
            character_slug = require_string(link.get("character"), f"{prefix}.character")
            role = link.get("role", "supporting")
            if role not in {choice for choice, _ in TitleCharacter.ROLE_CHOICES}:
                raise CommandError(f"{prefix}.role: неизвестное значение")
            if character_slug in linked_characters:
                raise CommandError(f"{prefix}.character: повторяющийся персонаж {character_slug}")
            linked_characters.add(character_slug)
        episodes = item.get("episodes", [])
        if not isinstance(episodes, list):
            raise CommandError(f"titles[{index}].episodes: ожидается массив")
        numbers = set()
        for episode_index, episode in enumerate(episodes):
            number = episode.get("number") if isinstance(episode, dict) else None
            if not isinstance(number, int) or isinstance(number, bool) or number < 1 or number in numbers:
                raise CommandError(f"titles[{index}].episodes[{episode_index}].number: неверный или повторяющийся номер")
            numbers.add(number)
            validate_translations(
                episode.get("translations", {}),
                f"titles[{index}].episodes[{episode_index}].translations",
                require_name=False,
            )
            sources = episode.get("sources", [])
            if not isinstance(sources, list):
                raise CommandError(f"titles[{index}].episodes[{episode_index}].sources: ожидается массив")
            for source_index, source in enumerate(sources):
                prefix = f"titles[{index}].episodes[{episode_index}].sources[{source_index}]"
                if not isinstance(source, dict):
                    raise CommandError(f"{prefix}: ожидается объект")
                require_string(source.get("provider"), f"{prefix}.provider")
                require_string(source.get("name"), f"{prefix}.name")
                url = require_string(source.get("url"), f"{prefix}.url")
                if not url.startswith("https://"):
                    raise CommandError(f"{prefix}.url: разрешён только HTTPS")
                if source.get("kind", "sub") not in {choice for choice, _ in Source.KIND_CHOICES}:
                    raise CommandError(f"{prefix}.kind: неизвестное значение")
                if source.get("availability", "available") not in {choice for choice, _ in Source.AVAILABILITY_CHOICES}:
                    raise CommandError(f"{prefix}.availability: неизвестное значение")
    return payload


def validate_translations(translations, path, *, require_name=True):
    if not isinstance(translations, dict):
        raise CommandError(f"{path}: ожидается объект с кодами языков")
    for language, value in translations.items():
        if language not in SUPPORTED_LANGUAGES or not isinstance(value, dict):
            raise CommandError(f"{path}.{language}: неподдерживаемый язык или формат")
        if require_name and "name" not in value:
            raise CommandError(f"{path}.{language}.name: обязательное поле")
        if "name" in value:
            require_string(value["name"], f"{path}.{language}.name")


def apply_payload(payload):
    stats = {key: 0 for key in ["genres", "franchises", "characters", "providers", "titles", "episodes", "sources", "title_characters", "translations"]}
    for item in payload.get("genres", []):
        genre = Genre.objects.update_or_create(slug=require_string(item.get("slug"), "genres.slug"), defaults={"name": require_string(item.get("name"), "genres.name")})[0]
        values = {"en": {"name": item["name"]}, **item.get("translations", {})}
        for language, value in values.items():
            GenreTranslation.objects.update_or_create(genre=genre, language=language, defaults={"name": value["name"]})
            stats["translations"] += 1
        stats["genres"] += 1
    for item in payload.get("franchises", []):
        franchise = Franchise.objects.update_or_create(
            slug=require_string(item.get("slug"), "franchises.slug"),
            defaults={"name": require_string(item.get("name"), "franchises.name"), "description": str(item.get("description", "")), "sort_order": int(item.get("sort_order", 0))},
        )[0]
        values = {"en": {"name": item["name"], "description": str(item.get("description", ""))}, **item.get("translations", {})}
        for language, value in values.items():
            FranchiseTranslation.objects.update_or_create(franchise=franchise, language=language, defaults={"name": value["name"], "description": str(value.get("description", ""))})
            stats["translations"] += 1
        stats["franchises"] += 1
    for item in payload.get("characters", []):
        character = Character.objects.update_or_create(
            slug=require_string(item.get("slug"), "characters.slug"),
            defaults={
                "name": require_string(item.get("name"), "characters.name"),
                "original_name": str(item.get("original_name", "")),
                "description": str(item.get("description", "")),
                "image_url": str(item.get("image_url", "")),
            },
        )[0]
        values = {"en": {"name": item["name"]}, **item.get("translations", {})}
        for language, value in values.items():
            CharacterTranslation.objects.update_or_create(
                character=character, language=language,
                defaults={"name": value["name"], "description": str(value.get("description", ""))},
            )
            stats["translations"] += 1
        stats["characters"] += 1
    for item in payload.get("providers", []):
        provider, created = Provider.objects.get_or_create(
            slug=require_string(item.get("slug"), "providers.slug"),
            defaults={"name": require_string(item.get("name"), "providers.name"), "is_enabled": False},
        )
        provider.name = require_string(item.get("name"), "providers.name")
        provider.website_url = str(item.get("website_url", ""))
        adapter, config, hosts = validate_provider_configuration(
            item.get("playback_adapter"), item.get("playback_config", {}), item.get("allowed_hosts", [])
        )
        provider.allowed_hosts = hosts
        provider.playback_adapter = adapter
        provider.playback_config = config
        if created:
            provider.is_enabled = False
        provider.save()
        stats["providers"] += 1
    for item in payload.get("titles", []):
        franchise = Franchise.objects.filter(slug=item.get("franchise")).first() if item.get("franchise") else None
        if item.get("franchise") and franchise is None:
            raise CommandError(f"Тайтл {item['slug']}: franchise {item['franchise']} не найдена")
        requested_genres = set(item.get("genres", []))
        genres = list(Genre.objects.filter(slug__in=requested_genres))
        found_genres = {genre.slug for genre in genres}
        if found_genres != requested_genres:
            raise CommandError(f"Тайтл {item['slug']}: genres не найдены: {sorted(requested_genres - found_genres)}")
        defaults = {
            "name": item["name"], "original_name": str(item.get("original_name", "")),
            "synopsis": str(item.get("synopsis", "")), "title_type": item.get("title_type", "anime"),
            "status": item.get("status", "planned"), "year": item.get("year"), "poster_url": str(item.get("poster_url", "")),
            "franchise": franchise,
        }
        title, _ = Title.objects.update_or_create(slug=item["slug"], defaults=defaults)
        values = {"en": {"name": item["name"], "synopsis": str(item.get("synopsis", ""))}, **item.get("translations", {})}
        for language, value in values.items():
            TitleTranslation.objects.update_or_create(title=title, language=language, defaults={"name": value["name"], "synopsis": str(value.get("synopsis", ""))})
            stats["translations"] += 1
        title.genres.set(genres)
        for link in item.get("characters", []):
            character = Character.objects.filter(slug=link["character"]).first()
            if character is None:
                raise CommandError(f"Тайтл {item['slug']}: character {link['character']} не найден")
            TitleCharacter.objects.update_or_create(
                title=title, character=character,
                defaults={"role": link.get("role", "supporting"), "sort_order": int(link.get("sort_order", 0))},
            )
            stats["title_characters"] += 1
        stats["titles"] += 1
        for episode_item in item.get("episodes", []):
            air_date = parse_date(episode_item["air_date"]) if episode_item.get("air_date") else None
            if episode_item.get("air_date") and air_date is None:
                raise CommandError(f"{title.slug} episode {episode_item['number']}: неверная air_date")
            episode, _ = Episode.objects.update_or_create(
                title=title, number=episode_item["number"],
                defaults={"name": str(episode_item.get("name", "")), "synopsis": str(episode_item.get("synopsis", "")), "air_date": air_date},
            )
            values = {"en": {"name": str(episode_item.get("name", "")), "synopsis": str(episode_item.get("synopsis", ""))}, **episode_item.get("translations", {})}
            for language, value in values.items():
                EpisodeTranslation.objects.update_or_create(episode=episode, language=language, defaults={"name": str(value.get("name", "")), "synopsis": str(value.get("synopsis", ""))})
                stats["translations"] += 1
            stats["episodes"] += 1
            for source_item in episode_item.get("sources", []):
                provider = Provider.objects.filter(slug=source_item["provider"]).first()
                if provider is None:
                    raise CommandError(f"Источник {source_item['name']}: provider {source_item['provider']} не найден")
                candidate = Source(provider=provider, url=source_item["url"])
                if not source_url_allowed(candidate):
                    raise CommandError(f"Источник {source_item['name']}: URL не соответствует provider allowlist")
                Source.objects.update_or_create(
                    episode=episode, name=source_item["name"], kind=source_item.get("kind", "sub"),
                    defaults={"provider": provider, "url": source_item["url"], "availability": source_item.get("availability", "available"), "availability_reason": str(source_item.get("availability_reason", ""))},
                )
                stats["sources"] += 1
    return stats


class Command(BaseCommand):
    help = "Validate and optionally atomically import AniCast catalog JSON."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--apply", action="store_true", help="Persist validated changes. Default is dry-run with rollback.")

    def handle(self, *args, **options):
        path = options["file"]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"Не удалось прочитать JSON: {error}") from error
        validate_payload(payload)
        with transaction.atomic():
            stats = apply_payload(payload)
            if not options["apply"]:
                transaction.set_rollback(True)
        mode = "APPLIED" if options["apply"] else "DRY-RUN"
        summary = ", ".join(f"{key}={value}" for key, value in stats.items())
        self.stdout.write(self.style.SUCCESS(f"{mode}: {summary}"))
