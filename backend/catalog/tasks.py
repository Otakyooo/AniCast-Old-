from celery import shared_task
import logging
import time
from django.utils import timezone

from .health import check_source
from .models import Source, SourceHealthCheck
from common.metrics import increment

logger = logging.getLogger("anicast.providers")


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


@shared_task
def check_provider_sources():
    checked = failed = transitions = 0
    queryset = Source.objects.filter(
        provider__is_enabled=True,
        availability__in=["available", "provider_error"],
    ).select_related("provider")
    for source in queryset:
        result = check_source(source)
        increment("source_checks", "healthy" if result.is_healthy else "failed")
        increment("source_duration_ms_sum", value=result.latency_ms)
        increment("source_duration_count")
        checked += 1
        SourceHealthCheck.objects.create(
            source=source,
            is_healthy=result.is_healthy,
            http_status=result.http_status,
            latency_ms=result.latency_ms,
            error=result.error,
        )
        source.last_checked_at = timezone.now()
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
        source.save(update_fields=[
            "last_checked_at", "last_http_status", "consecutive_failures", "availability", "availability_reason"
        ])
    logger.info("provider check batch completed", extra={
        "event": "provider_check_batch_completed", "checked": checked, "failed": failed,
        "transitions": transitions,
    })
    return {"checked": checked, "failed": failed}
