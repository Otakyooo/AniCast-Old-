"""Editor-facing dashboard for the content admin (functional concept §16).

The daily workspace should surface what needs attention — open complaints,
broken sources, episodes without dates, pending moderation and poster
quality gaps — before the editor dives into a specific changelist. All
numbers here are bounded read-only counts; nothing mutates state and the
audit trail of every ModelAdmin action stays untouched.
"""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import path, reverse

from catalog import posters
from catalog.models import Episode, Source, SourceReport, Title
from community.models import TitleReview


def _changelist(route: str, query: str = "") -> str:
    url = reverse(route)
    return f"{url}?{query}" if query else url


def _poster_tier_counts() -> dict[str, int]:
    """Tier histogram over stored poster URLs plus titles without any."""
    counts = {"maximum": 0, "large": 0, "kitsu": 0, "fallback": 0, "missing": 0}
    seen = 0
    urls = Title.objects.exclude(poster_url="").values_list("poster_url", flat=True).iterator(chunk_size=500)
    for poster_url in urls:
        seen += 1
        tier = posters.current_tier(poster_url)
        if tier == posters.TIER_MAXIMUM:
            counts["maximum"] += 1
        elif tier == posters.TIER_LARGE:
            counts["large"] += 1
        elif tier == posters.TIER_KITSU:
            counts["kitsu"] += 1
        elif tier == posters.TIER_FALLBACK:
            counts["fallback"] += 1
        else:
            counts["missing"] += 1
    counts["missing"] += Title.objects.count() - seen
    return counts


def build_dashboard() -> list[dict[str, Any]]:
    """One entry per attention area; ``tone`` drives the template colour."""
    new_reports = SourceReport.objects.filter(status=SourceReport.Status.NEW).count()
    reviewing_reports = SourceReport.objects.filter(status=SourceReport.Status.REVIEWING).count()
    provider_errors = Source.objects.filter(availability="provider_error").count()
    episodes_without_date = Episode.objects.filter(air_date__isnull=True).count()
    pending_reviews = TitleReview.objects.filter(status=TitleReview.Status.PENDING).count()
    tiers = _poster_tier_counts()
    below_maximum = tiers["fallback"] + tiers["missing"]

    return [
        {
            "label": "Новые жалобы",
            "value": new_reports,
            "hint": f"{reviewing_reports} на проверке",
            "tone": "danger" if new_reports else "ok",
            "url": _changelist("admin:catalog_sourcereport_changelist", "status__exact=new"),
        },
        {
            "label": "Источники с ошибкой провайдера",
            "value": provider_errors,
            "hint": "playback закрыт автоматически",
            "tone": "danger" if provider_errors else "ok",
            "url": _changelist("admin:catalog_source_changelist", "availability__exact=provider_error"),
        },
        {
            "label": "Эпизоды без даты выхода",
            "value": episodes_without_date,
            "hint": "не попадают в расписание",
            "tone": "warn" if episodes_without_date else "ok",
            "url": _changelist("admin:catalog_episode_changelist", "air_date__isnull=True"),
        },
        {
            "label": "Рецензии на модерации",
            "value": pending_reviews,
            "hint": "публично не видны",
            "tone": "warn" if pending_reviews else "ok",
            "url": _changelist("admin:community_titlereview_changelist", "status__exact=pending"),
        },
        {
            "label": "Постеры ниже максимума",
            "value": below_maximum,
            "hint": f"s:{tiers['fallback']} · нет:{tiers['missing']} · k:{tiers['kitsu']} · l:{tiers['large']}",
            "tone": "warn" if below_maximum else "ok",
            "url": _changelist("admin:catalog_title_changelist"),
        },
    ]


def staff_index(request: HttpRequest) -> HttpResponse:
    """Shadow of ``admin.site.index`` that adds the summary context."""
    return admin.site.index(request, extra_context={"dashboard": build_dashboard()})


def shadowed_admin_urls() -> tuple[list[Any], str, str]:
    """Default ``/staff/`` urlconf with the index replaced by :func:`staff_index`.

    Everything else — permissions, login flow, audit logging — is the stock
    admin, so existing rights and ModelAdmin behaviour stay exactly as they are.
    """
    patterns, app_namespace, instance_namespace = admin.site.urls
    kept = [pattern for pattern in patterns if getattr(pattern, "name", None) != "index"]
    shadowed = [path("", admin.site.admin_view(staff_index), name="index"), *kept]
    return shadowed, app_namespace, instance_namespace
