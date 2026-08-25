import hmac
from collections.abc import Iterable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_safe

PREFIX = "anicast:metrics:v1"
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "OTHER")
HTTP_ENDPOINTS = ("api", "health", "metrics", "staff", "other")
STATUS_FAMILIES = ("2xx", "3xx", "4xx", "5xx")
TASKS = (
    "catalog.tasks.check_provider_sources",
    "catalog.tasks.refresh_title_posters",
    "push.tasks.dispatch_episode_notifications",
    "other",
)
TASK_RESULTS = ("success", "failure", "retry")
POSTER_RESULTS = ("maximum", "large", "kitsu", "original", "mirrored", "current", "unavailable", "invalid", "error")


def increment(metric: str, *labels: str, value: int = 1) -> None:
    key = ":".join((PREFIX, metric, *labels))
    try:
        if cache.add(key, value, timeout=None):
            return
        cache.incr(key, value)
    except Exception:
        # Telemetry must never affect the application path it observes.
        return


def value(metric: str, *labels: str) -> int:
    try:
        return int(cache.get(":".join((PREFIX, metric, *labels)), 0))
    except Exception:
        return 0


def endpoint_group(path: str) -> str:
    if path.startswith("/api/"):
        return "api"
    if path.startswith("/health/"):
        return "health"
    if path == "/internal/metrics":
        return "metrics"
    if path.startswith("/staff") or path.startswith("/static/"):
        return "staff"
    return "other"


def observe_http(method: str, path: str, status: int, duration_ms: int) -> None:
    safe_method = method if method in HTTP_METHODS else "OTHER"
    endpoint = endpoint_group(path)
    status_family = f"{status // 100}xx" if 200 <= status < 600 else "5xx"
    increment("http_requests", safe_method, endpoint, status_family)
    increment("http_duration_ms_sum", endpoint, value=max(duration_ms, 0))
    increment("http_duration_count", endpoint)


def _sample(name: str, labels: dict[str, str], sample_value: int) -> str:
    encoded = ",".join(f'{key}="{label}"' for key, label in labels.items())
    return f"{name}{{{encoded}}} {sample_value}"


def _family(name: str, help_text: str, metric_type: str, samples: Iterable[str]) -> list[str]:
    return [f"# HELP {name} {help_text}", f"# TYPE {name} {metric_type}", *samples]


def render_metrics() -> str:
    lines: list[str] = []
    http_samples = []
    for method in HTTP_METHODS:
        for endpoint in HTTP_ENDPOINTS:
            for status_family in STATUS_FAMILIES:
                count = value("http_requests", method, endpoint, status_family)
                if count:
                    http_samples.append(_sample("anicast_http_requests_total", {
                        "method": method, "endpoint": endpoint, "status_family": status_family
                    }, count))
    lines += _family("anicast_http_requests_total", "Completed HTTP requests.", "counter", http_samples)

    duration_count = [_sample("anicast_http_request_duration_seconds_count", {"endpoint": endpoint}, value("http_duration_count", endpoint)) for endpoint in HTTP_ENDPOINTS]
    duration_sum = [f'anicast_http_request_duration_seconds_sum{{endpoint="{endpoint}"}} {value("http_duration_ms_sum", endpoint) / 1000:.3f}' for endpoint in HTTP_ENDPOINTS]
    lines += _family("anicast_http_request_duration_seconds", "HTTP request duration.", "summary", [*duration_count, *duration_sum])

    task_samples = []
    for task in TASKS:
        for result in TASK_RESULTS:
            count = value("celery_tasks", task, result)
            if count:
                task_samples.append(_sample("anicast_celery_tasks_total", {"task": task, "result": result}, count))
    lines += _family("anicast_celery_tasks_total", "Celery task outcomes.", "counter", task_samples)

    source_samples = [_sample("anicast_source_checks_total", {"result": result}, value("source_checks", result)) for result in ("healthy", "failed")]
    lines += _family("anicast_source_checks_total", "Provider source check outcomes.", "counter", source_samples)
    lines += _family("anicast_source_check_duration_seconds", "Provider source check duration.", "summary", [
        f'anicast_source_check_duration_seconds_count {value("source_duration_count")}',
        f'anicast_source_check_duration_seconds_sum {value("source_duration_ms_sum") / 1000:.3f}',
    ])
    delivery_samples = [_sample("anicast_notification_deliveries_total", {"result": result}, value("notification_deliveries", result)) for result in ("sent", "failed")]
    lines += _family("anicast_notification_deliveries_total", "Notification delivery outcomes.", "counter", delivery_samples)

    poster_samples = [_sample("anicast_poster_refresh_total", {"result": result}, value("poster_refresh", result)) for result in POSTER_RESULTS]
    lines += _family("anicast_poster_refresh_total", "Poster refresh outcomes.", "counter", poster_samples)

    try:
        from common.availability import availability_samples

        up_samples, uptime_samples = availability_samples()
        lines += _family("anicast_availability_up", "Latest availability probe outcome per target (1 = up).", "gauge", up_samples)
        lines += _family("anicast_availability_uptime_percent", "Uptime percentage per target over the last 24 hours.", "gauge", uptime_samples)
    except Exception:
        # Telemetry must never affect the application path it observes.
        pass

    from catalog.models import Provider, Source

    provider_samples = [_sample("anicast_providers", {"enabled": str(enabled).lower()}, Provider.objects.filter(is_enabled=enabled).count()) for enabled in (True, False)]
    lines += _family("anicast_providers", "Configured providers.", "gauge", provider_samples)
    source_samples = [_sample("anicast_sources", {"availability": availability}, Source.objects.filter(availability=availability).count()) for availability, _ in Source.AVAILABILITY_CHOICES]
    lines += _family("anicast_sources", "Sources by availability.", "gauge", source_samples)
    return "\n".join(lines) + "\n"


@require_safe
def metrics_view(request: HttpRequest) -> HttpResponse:
    token = settings.METRICS_BEARER_TOKEN
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {token}"
    if not token or not hmac.compare_digest(supplied, expected):
        return HttpResponse(status=404)
    try:
        body = render_metrics()
    except Exception:
        return HttpResponse("metrics unavailable\n", status=503, content_type="text/plain")
    response = HttpResponse(body, content_type="text/plain; version=0.0.4; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response
