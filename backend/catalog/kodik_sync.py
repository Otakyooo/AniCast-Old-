import hashlib
import re
from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from .kodik import PLAYER_HOST, normalize_player_url, search_by_shikimori
from .models import Creator, Episode, Provider, Source, Title, TitleCredit
from .playback import source_url_allowed, validate_provider_configuration


SHIKIMORI_SLUG = re.compile(r"^(\d+)-")
KODIK_ID = re.compile(r"^(?:movie|serial)-\d+$")
CREDIT_FIELDS = {
    "directors": "director",
    "producers": "producer",
    "writers": "writer",
    "composers": "composer",
    "designers": "designer",
}


@dataclass
class SyncResult:
    title: str
    discovered: int = 0
    persisted: int = 0
    created_episodes: int = 0
    scheduled: int = 0
    credits: int = 0
    stale: int = 0
    skipped: int = 0


def ensure_provider(*, activate: bool = False, rights_reference: str = "") -> Provider:
    provider, _ = Provider.objects.get_or_create(
        slug="kodik",
        defaults={
            "name": "Kodik",
            "website_url": "https://bd.kodikres.com",
            "allowed_hosts": [PLAYER_HOST],
            "playback_adapter": "iframe_embed",
            "playback_config": {},
        },
    )
    validate_provider_configuration(provider.playback_adapter, provider.playback_config, provider.allowed_hosts)
    if provider.playback_adapter != "iframe_embed" or provider.allowed_hosts != [PLAYER_HOST]:
        raise ValueError("Kodik provider must use iframe_embed and the exact kodikplayer.com allowlist")
    if activate:
        if not rights_reference.strip():
            raise ValueError("A rights reference is required to activate Kodik playback")
        provider.is_enabled = True
        provider.rights_reference = rights_reference.strip()[:240]
        provider.rights_verified_at = timezone.now()
        provider.save(update_fields=["is_enabled", "rights_reference", "rights_verified_at", "updated_at"])
    return provider


def _creator(name: str) -> Creator:
    normalized = " ".join(name.split())[:200]
    existing = Creator.objects.filter(name=normalized).first()
    if existing:
        return existing
    base = slugify(normalized, allow_unicode=True)[:190] or "creator"
    slug = base
    if Creator.objects.filter(slug=slug).exists():
        slug = f"{base[:180]}-{hashlib.sha1(normalized.encode()).hexdigest()[:8]}"
    return Creator.objects.create(name=normalized, slug=slug)


def _sync_credits(title: Title, material: dict) -> int:
    active: set[tuple[int, str]] = set()
    position = 0
    for field, role in CREDIT_FIELDS.items():
        values = material.get(field) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            name = value.get("name") if isinstance(value, dict) else value
            if not isinstance(name, str) or not name.strip():
                continue
            creator = _creator(name)
            TitleCredit.objects.update_or_create(
                title=title,
                creator=creator,
                role=role,
                defaults={"source": "kodik", "sort_order": position},
            )
            active.add((creator.id, role))
            position += 1
    stale = TitleCredit.objects.filter(title=title, source="kodik")
    if active:
        for credit in stale:
            if (credit.creator_id, credit.role) not in active:
                credit.delete()
    return len(active)


def _material(results: list[dict]) -> dict:
    for item in results:
        value = item.get("material_data")
        if isinstance(value, dict) and value:
            return value
    return {}


@transaction.atomic
def sync_title(
    title: Title,
    *,
    season: int = 1,
    limit: int = 100,
    activate: bool = False,
    rights_reference: str = "",
) -> SyncResult:
    match = SHIKIMORI_SLUG.match(title.slug)
    if match is None:
        raise ValueError("Title slug does not contain a Shikimori id")
    page = search_by_shikimori(
        int(match.group(1)), limit=limit, season=season, with_material_data=True,
    )
    results = page.results
    complete_snapshot = page.total <= len(results)
    provider = ensure_provider(activate=activate, rights_reference=rights_reference)
    outcome = SyncResult(title=title.slug)
    material = _material(results)

    duration = material.get("duration")
    if isinstance(duration, int) and 0 < duration < 1000 and title.duration_minutes != duration:
        title.duration_minutes = duration
        title.save(update_fields=["duration_minutes"])
    outcome.credits = _sync_credits(title, material)

    episodes = {episode.number: episode for episode in Episode.objects.filter(title=title)}
    active_source_ids: list[int] = []
    for item in results:
        external_id = item.get("id")
        translation = item.get("translation") or {}
        translation_id = translation.get("id")
        if not isinstance(external_id, str) or not KODIK_ID.fullmatch(external_id) or type(translation_id) is not int:
            outcome.skipped += 1
            continue
        source_external_id = f"{external_id}:s{season}:t{translation_id}"
        translation_title = str(translation.get("title") or "Kodik").strip()[:100]
        kind = "sub" if translation.get("type") == "subtitles" else "dub"
        season_data = (item.get("seasons") or {}).get(str(season)) or {}
        episode_links = season_data.get("episodes") or {}
        if not episode_links and item.get("link"):
            episode_links = {"1": item["link"]}
        for raw_number, episode_data in episode_links.items():
            try:
                number = int(raw_number)
            except (TypeError, ValueError):
                outcome.skipped += 1
                continue
            raw_url = episode_data.get("link") if isinstance(episode_data, dict) else episode_data
            url = normalize_player_url(raw_url)
            candidate = Source(provider=provider, url=url or "")
            if number < 1 or url is None or not source_url_allowed(candidate):
                outcome.skipped += 1
                continue
            episode = episodes.get(number)
            if episode is None:
                episode = Episode.objects.create(title=title, number=number)
                episodes[number] = episode
                outcome.created_episodes += 1
            outcome.discovered += 1
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
            outcome.persisted += 1

    next_episode_at = material.get("next_episode_at")
    episodes_aired = material.get("episodes_aired")
    moment = parse_datetime(next_episode_at) if isinstance(next_episode_at, str) else None
    if moment and timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    if moment and isinstance(episodes_aired, int) and episodes_aired >= 0:
        number = episodes_aired + 1
        episode, created = Episode.objects.get_or_create(title=title, number=number)
        if created:
            outcome.created_episodes += 1
        if episode.air_at != moment:
            episode.air_at = moment
            episode.save(update_fields=["air_at"])
        outcome.scheduled = 1

    if complete_snapshot:
        stale = Source.objects.filter(
            provider=provider,
            episode__title=title,
            external_id__contains=f":s{season}:",
        ).exclude(id__in=active_source_ids)
        outcome.stale = stale.update(
            availability="unavailable",
            availability_reason="Kodik sync: source no longer returned",
        )
    return outcome
