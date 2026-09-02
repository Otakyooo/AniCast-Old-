from celery import shared_task
import logging
import time
from datetime import timedelta

from django.utils import timezone

from .health import check_source
from .models import Source, SourceHealthCheck
from common.metrics import increment

logger = logging.getLogger("anicast.providers")


@shared_task(soft_time_limit=520, time_limit=570)
def sync_kodik_library(limit: int = 20) -> dict[str, int]:
    """Continuously refresh a bounded slice of the local AniCast library."""
    from django.core.cache import cache

    from .kodik import KodikAPIError
    from .kodik_sync import SHIKIMORI_SLUG, sync_title
    from .models import Title

    batch_limit = max(1, min(int(limit), 50))
    cursor = int(cache.get("catalog:kodik-sync-cursor", 0) or 0)
    titles = list(Title.objects.filter(id__gt=cursor).order_by("id")[:batch_limit])
    if not titles:
        cursor = 0
        titles = list(Title.objects.order_by("id")[:batch_limit])
    totals = {"titles": 0, "failed": 0, "persisted": 0, "scheduled": 0, "credits": 0}
    for title in titles:
        if not SHIKIMORI_SLUG.match(title.slug):
            continue
        try:
            result = sync_title(title)
        except (KodikAPIError, ValueError):
            totals["failed"] += 1
            logger.exception("Kodik title sync failed", extra={"event": "kodik_sync_failed", "title_id": title.id})
            continue
        totals["titles"] += 1
        totals["persisted"] += result.persisted
        totals["scheduled"] += result.scheduled
        totals["credits"] += result.credits
    cache.set("catalog:kodik-sync-cursor", titles[-1].id if titles else cursor, timeout=None)
    logger.info("Kodik library slice synchronized", extra={"event": "kodik_sync_completed", **totals})
    return totals


@shared_task(soft_time_limit=480, time_limit=520)
def sync_episode_metadata_library(limit: int = 3) -> dict[str, int]:
    """Continuously fill trustworthy episode names and broadcast dates.

    The deliberately small slice respects Jikan's public rate limit. Exact
    future timestamps remain owned by Kodik; Jikan only supplies episode names
    and confirmed calendar dates.
    """
    from django.core.cache import cache

    from .episode_metadata import EpisodeMetadataError, sync_title_episode_metadata
    from .models import Title

    batch_limit = max(1, min(int(limit), 3))
    cursor = int(cache.get("catalog:episode-metadata-cursor", 0) or 0)
    from django.db.models import Q

    candidates = Title.objects.filter(
        Q(episodes__name="") | Q(episodes__air_date__isnull=True, episodes__air_at__isnull=True)
    ).distinct()
    titles = list(candidates.filter(id__gt=cursor).order_by("id")[:batch_limit])
    if not titles:
        cursor = 0
        titles = list(candidates.order_by("id")[:batch_limit])
    totals = {"titles": 0, "failed": 0, "pages": 0, "episodes": 0, "named": 0, "dated": 0}
    for title in titles:
        try:
            result = sync_title_episode_metadata(title)
        except (EpisodeMetadataError, ValueError):
            totals["failed"] += 1
            logger.exception("Episode metadata sync failed", extra={
                "event": "episode_metadata_sync_failed", "title_id": title.id,
            })
            continue
        totals["titles"] += 1
        for key in ("pages", "episodes", "named", "dated"):
            totals[key] += getattr(result, key)
    cache.set("catalog:episode-metadata-cursor", titles[-1].id if titles else cursor, timeout=None)
    logger.info("Episode metadata slice synchronized", extra={
        "event": "episode_metadata_sync_completed", **totals,
    })
    return totals


@shared_task(soft_time_limit=480, time_limit=520)
def sync_character_library(limit: int = 5) -> dict[str, int]:
    """Converge truncated legacy cast lists to the provider's complete roles."""
    from django.core.cache import cache

    from .character_sync import CharacterSyncError, sync_title_characters
    from .models import Title

    batch_limit = max(1, min(int(limit), 10))
    cursor = int(cache.get("catalog:character-sync-cursor", 0) or 0)
    titles = list(Title.objects.filter(id__gt=cursor).order_by("id")[:batch_limit])
    if not titles:
        cursor = 0
        titles = list(Title.objects.order_by("id")[:batch_limit])
    totals = {"titles": 0, "failed": 0, "discovered": 0, "created": 0, "linked": 0}
    for title in titles:
        try:
            result = sync_title_characters(title)
        except (CharacterSyncError, OSError, ValueError):
            totals["failed"] += 1
            logger.exception("Character sync failed", extra={"event": "character_sync_failed", "title_id": title.id})
            continue
        totals["titles"] += 1
        for key in ("discovered", "created", "linked"):
            totals[key] += getattr(result, key)
    cache.set("catalog:character-sync-cursor", titles[-1].id if titles else cursor, timeout=None)
    logger.info("Character slice synchronized", extra={"event": "character_sync_completed", **totals})
    return totals


@shared_task(soft_time_limit=1500, time_limit=1800)
def refresh_title_posters(limit: int = 0) -> dict[str, int]:
    """Scheduled poster upgrade pass.

    ``limit=0`` lets the batch run until its time budget is spent; pass a
    positive number to cap the processed titles explicitly. A cache lock
    keeps a manual trigger and the scheduled run from doubling the probe
    rate against Jikan's rate limits.
    """
    from django.core.cache import cache

    from . import posters

    lock_key = "catalog:poster-refresh-lock"
    if not cache.add(lock_key, "1", timeout=1800):
        logger.info("poster refresh skipped: another batch holds the lock", extra={
            "event": "poster_refresh_skipped_locked",
        })
        return {}
    try:
        deadline = time.monotonic() + posters.BATCH_TIME_BUDGET_SECONDS
        outcomes = posters.refresh_batch(limit=int(limit), apply_changes=True, deadline=deadline)
    finally:
        cache.delete(lock_key)
    counts: dict[str, int] = {}
    for result, _ in outcomes:
        counts[result] = counts.get(result, 0) + 1
    logger.info("poster refresh batch completed", extra={
        "event": "poster_refresh_batch_completed",
        "processed": len(outcomes),
        **{f"result_{key}": count for key, count in sorted(counts.items())},
    })
    return counts


HEALTH_CHECK_RETENTION_DAYS = 14
HEALTH_CHECK_BATCH_CAP = 150
HEALTH_CHECK_TIME_BUDGET_SECONDS = 420


@shared_task(soft_time_limit=520, time_limit=570)
def check_provider_sources(limit: int = HEALTH_CHECK_BATCH_CAP) -> dict[str, int]:
    """Probe a bounded slice of provider sources and prune old health rows.

    The pass used to walk every enabled non-iframe source in one run. With ~29k
    sources and a 10-second HEAD timeout each, that could not finish inside the
    Celery soft limit: the task was killed mid-batch every ten minutes, leaving
    the tail of the catalog unchecked and writing one SourceHealthCheck row per
    source per run with no retention.

    A cursor walks the whole catalog across runs, a wall-clock budget stops new
    probes before the soft limit fires, and the ledger keeps two weeks of
    history — long enough for the staff dashboard's rolling windows.
    """
    from django.core.cache import cache

    batch_limit = max(1, min(int(limit), HEALTH_CHECK_BATCH_CAP))
    deadline = time.monotonic() + HEALTH_CHECK_TIME_BUDGET_SECONDS
    cursor = int(cache.get("catalog:source-check-cursor", 0) or 0)
    candidates = Source.objects.filter(
        provider__is_enabled=True,
        availability__in=["available", "provider_error"],
    ).exclude(provider__playback_adapter="iframe_embed").select_related("provider").order_by("id")
    sources = list(candidates.filter(id__gt=cursor)[:batch_limit])
    if not sources:
        # Wrap around so a shrinking catalog cannot strand the cursor past the
        # last id and stop checking altogether.
        cursor = 0
        sources = list(candidates[:batch_limit])

    checked = failed = transitions = 0
    health_rows = []
    now = timezone.now()
    for source in sources:
        if time.monotonic() >= deadline:
            break
        result = check_source(source)
        increment("source_checks", "healthy" if result.is_healthy else "failed")
        increment("source_duration_ms_sum", value=result.latency_ms)
        increment("source_duration_count")
        checked += 1
        health_rows.append(
            SourceHealthCheck(
                source=source,
                is_healthy=result.is_healthy,
                http_status=result.http_status,
                latency_ms=result.latency_ms,
                error=result.error,
            )
        )
        source.last_checked_at = now
        source.last_http_status = result.http_status
        previous_availability = source.availability
        if result.is_healthy:
            source.consecutive_failures = 0
            if source.availability == "provider_error" and source.availability_reason.startswith("Автопроверка:"):
                source.availability = "available"
                source.availability_reason = ""
        else:
            failed += 1
            source.consecutive_failures += 1
            if source.consecutive_failures >= 3:
                source.availability = "provider_error"
                source.availability_reason = f"Автопроверка: {result.error}"[:240]
        if source.availability != previous_availability:
            transitions += 1
            increment("source_state_transitions", source.availability)
            logger.warning("provider source state changed", extra={
                "event": "provider_source_state_changed", "source_id": source.pk,
                "result": source.availability,
            })
        cursor = source.id

    probed = sources[:checked]
    if probed:
        SourceHealthCheck.objects.bulk_create(health_rows)
        Source.objects.bulk_update(
            probed,
            ["last_checked_at", "last_http_status", "consecutive_failures", "availability", "availability_reason"],
        )
    cache.set("catalog:source-check-cursor", cursor, timeout=None)

    pruned, _ = SourceHealthCheck.objects.filter(
        checked_at__lt=now - timedelta(days=HEALTH_CHECK_RETENTION_DAYS)
    ).delete()
    logger.info("provider check batch completed", extra={
        "event": "provider_check_batch_completed", "checked": checked, "failed": failed,
        "transitions": transitions, "pruned": pruned,
    })
    return {"checked": checked, "failed": failed, "pruned": pruned}
