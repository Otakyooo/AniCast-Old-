import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.kodik import KodikAPIError, PLAYER_HOST, normalize_player_url, search_by_shikimori
from catalog.models import Episode, Provider, Source, Title
from catalog.playback import source_url_allowed, validate_provider_configuration


SHIKIMORI_SLUG = re.compile(r"^(\d+)-")
KODIK_ID = re.compile(r"^(?:movie|serial)-\d+$")


class Command(BaseCommand):
    help = "Discover Kodik episode players by Shikimori id. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("title_slug")
        parser.add_argument("--season", type=int, default=1)
        parser.add_argument("--translation-id", type=int)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        title = Title.objects.filter(slug=options["title_slug"]).first()
        if title is None:
            raise CommandError("Тайтл не найден")
        match = SHIKIMORI_SLUG.match(title.slug)
        if match is None:
            raise CommandError("Slug тайтла не содержит Shikimori id")
        season = options["season"]
        if season < 0:
            raise CommandError("Номер сезона должен быть неотрицательным")
        try:
            page = search_by_shikimori(int(match.group(1)), limit=options["limit"], season=season)
        except (KodikAPIError, ValueError) as error:
            raise CommandError(str(error)) from error

        results = page.results
        complete_snapshot = page.total <= len(results)
        translation_id = options["translation_id"]
        if translation_id is not None:
            results = [result for result in results if (result.get("translation") or {}).get("id") == translation_id]
        if not results and translation_id is None and not complete_snapshot:
            raise CommandError("Kodik не вернул подходящих материалов")

        with transaction.atomic():
            provider, created = Provider.objects.get_or_create(
                slug="kodik",
                defaults={
                    "name": "Kodik",
                    "website_url": "https://bd.kodikres.com",
                    "allowed_hosts": [PLAYER_HOST],
                    "playback_adapter": "iframe_embed",
                    "playback_config": {},
                    "is_enabled": False,
                },
            )
            try:
                validate_provider_configuration(provider.playback_adapter, provider.playback_config, provider.allowed_hosts)
            except ValueError as error:
                raise CommandError(f"Kodik provider настроен небезопасно: {error}") from error
            if provider.playback_adapter != "iframe_embed" or provider.allowed_hosts != [PLAYER_HOST]:
                raise CommandError("Kodik provider должен использовать iframe_embed и точный allowlist kodikplayer.com")

            episodes = {episode.number: episode for episode in Episode.objects.filter(title=title)}
            discovered = 0
            persisted = 0
            skipped = 0
            active_source_ids: list[int] = []
            for result in results:
                external_id = result.get("id")
                if not isinstance(external_id, str) or not KODIK_ID.fullmatch(external_id):
                    skipped += 1
                    continue
                translation = result.get("translation") or {}
                result_translation_id = translation.get("id")
                if type(result_translation_id) is not int or result_translation_id < 1:
                    skipped += 1
                    continue
                source_external_id = f"{external_id}:s{season}:t{result_translation_id}"
                translation_title = str(translation.get("title") or "Kodik").strip()[:100]
                kind = "sub" if translation.get("type") == "subtitles" else "dub"
                season_data = (result.get("seasons") or {}).get(str(season)) or {}
                episode_links = season_data.get("episodes") or {}
                if not episode_links and len(episodes) == 1 and result.get("link"):
                    episode_links = {str(next(iter(episodes))): result["link"]}
                for number, episode_data in episode_links.items():
                    try:
                        episode_number = int(number)
                    except (TypeError, ValueError):
                        skipped += 1
                        continue
                    raw_url = episode_data.get("link") if isinstance(episode_data, dict) else episode_data
                    url = normalize_player_url(raw_url)
                    episode = episodes.get(episode_number)
                    candidate = Source(provider=provider, url=url or "")
                    if episode is None or url is None or not source_url_allowed(candidate):
                        skipped += 1
                        continue
                    discovered += 1
                    source, _ = Source.objects.update_or_create(
                        provider=provider,
                        episode=episode,
                        external_id=source_external_id,
                        defaults={
                            "name": f"Kodik · {translation_title}"[:120],
                            "kind": kind,
                            "url": url,
                            "availability": "available",
                            "availability_reason": "",
                        },
                    )
                    active_source_ids.append(source.id)
                    persisted += 1
            stale = 0
            if complete_snapshot:
                stale_sources = Source.objects.filter(
                    provider=provider,
                    episode__title=title,
                    external_id__contains=f":s{season}:",
                ).exclude(id__in=active_source_ids)
                if translation_id is not None:
                    stale_sources = stale_sources.filter(external_id__endswith=f":t{translation_id}")
                stale = stale_sources.update(
                    availability="unavailable",
                    availability_reason="Kodik sync: source no longer returned",
                )
            if not options["apply"]:
                transaction.set_rollback(True)

        mode = "APPLIED" if options["apply"] else "DRY-RUN"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: title={title.slug}, season={season}, translations={len(results)}, "
                f"discovered={discovered}, persisted={persisted}, stale={stale}, skipped={skipped}, "
                f"complete_snapshot={complete_snapshot}, "
                f"provider_created={created}; rights grants untouched"
            )
        )
