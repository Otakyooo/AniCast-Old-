from celery import shared_task
from django.utils import timezone

from .health import check_source
from .models import Source, SourceHealthCheck


@shared_task
def check_provider_sources():
    checked = failed = 0
    queryset = Source.objects.filter(
        provider__is_enabled=True,
        availability__in=["available", "provider_error"],
    ).select_related("provider")
    for source in queryset:
        result = check_source(source)
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
        source.save(update_fields=[
            "last_checked_at", "last_http_status", "consecutive_failures", "availability", "availability_reason"
        ])
    return {"checked": checked, "failed": failed}
