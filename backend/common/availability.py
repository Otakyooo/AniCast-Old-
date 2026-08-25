"""Availability tracking in the style of public status pages.

Celery Beat probes every target once a minute and stores one
:class:`~common.models.AvailabilitySample` per target. The staff dashboard
aggregates the rows into current state, rolling-window uptime percentages and
the time since the last outage, so staff can answer "сколько сайт работает"
directly in the admin without reaching for Prometheus.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from common.models import AvailabilitySample

PROBE_TIMEOUT_S = 5
RETENTION_DAYS = 30


@dataclass(frozen=True)
class Target:
    key: str
    label: str
    url: str
    headers: dict[str, str]


def _targets() -> tuple[Target, ...]:
    site = settings.ANICAST_SITE_URL.rstrip("/")
    return (
        Target("site", "Сайт", f"{site}/", {}),
        Target("api", "API каталога", f"{site}/api/v1/titles/?page_size=1", {}),
        # Probed from inside the compose network; the header marks the hop
        # secure the same way Caddy does (SECURE_PROXY_SSL_HEADER).
        Target(
            "readiness",
            "Backend readiness",
            "http://backend:8000/health/ready",
            {"X-Forwarded-Proto": "https"},
        ),
    )


def probe_target(target: Target) -> dict:
    """One bounded HTTP probe; never raises, always returns sample fields."""
    started = time.perf_counter()
    status_code: int | None = None
    detail = ""
    ok = False
    request = urllib.request.Request(
        target.url,
        headers={"User-Agent": "anicast-uptime/1", **target.headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_S) as response:
            status_code = int(response.status)
            ok = status_code < 400
    except urllib.error.HTTPError as error:
        status_code = int(error.code)
        detail = f"HTTP {error.code}"
    except Exception as error:  # URLError/timeouts/ssl — any failure is downtime
        detail = (str(error) or type(error).__name__)[:120]
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "ok": ok,
        "latency_ms": latency_ms,
        "status_code": status_code,
        "detail": detail,
    }


def record_result(target_key: str, checked_at=None, **fields) -> AvailabilitySample:
    return AvailabilitySample.objects.create(
        target=target_key,
        checked_at=checked_at or timezone.now(),
        **fields,
    )


def probe_all() -> dict[str, bool]:
    """Probe every target once; a crashing probe must not skip its peers."""
    outcomes: dict[str, bool] = {}
    for target in _targets():
        try:
            sample = probe_target(target)
        except Exception as error:  # defensive: telemetry never breaks the beat
            sample = {"ok": False, "latency_ms": 0, "status_code": None, "detail": type(error).__name__}
        record_result(target.key, **sample)
        outcomes[target.key] = sample["ok"]
    return outcomes


def prune(now=None) -> int:
    """Drop raw samples beyond retention; aggregates need nothing older."""
    cutoff = (now or timezone.now()) - timedelta(days=RETENTION_DAYS)
    deleted, _ = AvailabilitySample.objects.filter(checked_at__lt=cutoff).delete()
    return deleted


def format_duration(delta: timedelta) -> str:
    total_seconds = max(int(delta.total_seconds()), 0)
    days, rest = divmod(total_seconds, 86_400)
    hours, minutes = divmod(rest // 60, 60)
    if days:
        return f"{days} д {hours:02d}:{minutes:02d}"
    return f"{hours:02d}:{minutes:02d}"


def summarize(target_key: str, now=None) -> dict:
    """Rolling-window availability summary for one target."""
    now = now or timezone.now()
    week_ago = now - timedelta(days=7)
    samples = list(
        AvailabilitySample.objects.filter(target=target_key, checked_at__gte=week_ago)
        .order_by("checked_at")
        .values("checked_at", "ok", "latency_ms")
    )

    def uptime_percent(window_start) -> str:
        window = [s for s in samples if s["checked_at"] >= window_start]
        if not window:
            return "—"
        share = 100.0 * sum(1 for s in window if s["ok"]) / len(window)
        return f"{share:.2f}%"

    currently_up = bool(samples and samples[-1]["ok"])
    last_failure_index = next(
        (index for index in range(len(samples) - 1, -1, -1) if not samples[index]["ok"]),
        -1,
    )
    streak_started = None
    last_incident = None
    if samples:
        if last_failure_index < 0:  # no outage ever recorded: up since first probe
            streak_started = samples[0]["checked_at"]
        elif last_failure_index == len(samples) - 1:  # failing right now
            streak_started = samples[last_failure_index]["checked_at"]
        else:
            streak_started = samples[last_failure_index + 1]["checked_at"]
            last_incident = samples[last_failure_index]["checked_at"]

    lines = []
    if currently_up and streak_started:
        lines.append(f"работает {format_duration(now - streak_started)}")
    if not currently_up and streak_started:
        lines.append(f"недоступен с {timezone.localtime(streak_started):%d.%m %H:%M}")
    if last_incident is not None:
        lines.append(f"последний сбой {timezone.localtime(last_incident):%d.%m %H:%M}")

    day_ago = now - timedelta(hours=24)
    day_window = [s for s in samples if s["checked_at"] >= day_ago]
    avg_latency = (
        round(sum(s["latency_ms"] for s in day_window) / len(day_window)) if day_window else None
    )
    return {
        "currently_up": currently_up,
        "uptime_24h": uptime_percent(day_ago),
        "uptime_7d": uptime_percent(week_ago),
        "avg_latency_ms": avg_latency,
        "samples_24h": len(day_window),
        "last_checked_at": samples[-1]["checked_at"] if samples else None,
        "detail_line": " · ".join(lines) or "данные собираются",
        "streak_started": streak_started,
        "last_incident": last_incident,
    }


def build_availability_dashboard(now=None) -> list[dict]:
    """Status-page style rows for the staff dashboard template."""
    from django.urls import reverse

    rows = []
    for target in _targets():
        summary = summarize(target.key, now=now)
        latest_ok = summary["currently_up"] if summary["uptime_24h"] != "—" else None
        checked_line = ""
        if summary["last_checked_at"] is not None:
            checked_line = f"проверено {timezone.localtime(summary['last_checked_at']):%H:%M}"
            if summary["avg_latency_ms"] is not None:
                checked_line += f" · ~{summary['avg_latency_ms']} мс"
            if summary["samples_24h"]:
                checked_line += f" · проб за 24ч: {summary['samples_24h']}"
        try:
            url = reverse("admin:common_availabilitysample_changelist")
            url += f"?target__exact={target.key}"
        except Exception:  # pragma: no cover — admin urls are always loaded in prod
            url = ""
        rows.append(
            {
                "label": target.label,
                "status_label": (
                    "Работает" if latest_ok else "Недоступен" if latest_ok is False else "Нет данных"
                ),
                "tone": "ok" if latest_ok else "danger" if latest_ok is False else "warn",
                "uptime_24h": summary["uptime_24h"],
                "uptime_7d": summary["uptime_7d"],
                "detail_line": summary["detail_line"],
                "checked_line": checked_line,
                "url": url,
            }
        )
    return rows


def availability_samples() -> tuple[list[str], list[str]]:
    """Prometheus samples: (up/down flags, 24h uptime percentages) per target."""

    def escape(label: str) -> str:
        return label.replace("\\", "\\\\").replace('"', '\\"')

    now = timezone.now()
    fresh_cutoff = now - timedelta(minutes=5)
    up_samples: list[str] = []
    uptime_samples: list[str] = []
    for target in _targets():
        latest = (
            AvailabilitySample.objects.filter(target=target.key)
            .order_by("-checked_at")
            .values_list("ok", flat=True)
            .first()
        )
        recent_exists = AvailabilitySample.objects.filter(
            target=target.key, checked_at__gte=fresh_cutoff
        ).exists()
        if latest is not None and recent_exists:
            up_samples.append(f'anicast_availability_up{{target="{escape(target.key)}"}} {1 if latest else 0}')
        summary = summarize(target.key, now=now)
        if summary["uptime_24h"] != "—":
            value = float(summary["uptime_24h"].rstrip("%"))
            uptime_samples.append(
                f'anicast_availability_uptime_percent{{target="{escape(target.key)}"}} {value:.2f}'
            )
    return up_samples, uptime_samples
