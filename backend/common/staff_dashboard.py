"""Editor-facing dashboard for the content admin (functional concept §16).

The daily workspace should surface what needs attention — open complaints,
broken sources, episodes without dates, pending moderation and poster
quality gaps — before the editor dives into a specific changelist. All
numbers here are bounded read-only counts; nothing mutates state and the
audit trail of every ModelAdmin action stays untouched.
"""

from typing import Any

from django.contrib import admin
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.urls import path, reverse

from catalog import posters
from catalog.models import Character, Creator, Episode, Source, SourceReport, Title, TitleCharacter
from community.models import TitleReview


def _availability_section() -> list[dict[str, Any]]:
    """Status-page rows; failures here must never break the admin index."""
    try:
        from common.availability import build_availability_dashboard

        return build_availability_dashboard()
    except Exception:
        return []


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


def _system_cards() -> list[dict[str, Any]]:
    """Background-system health from Redis counters (lifetime since reset)."""
    from common.metrics import TASKS, value

    failures = sum(value("celery_tasks", task, "failure") for task in TASKS)
    retries = sum(value("celery_tasks", task, "retry") for task in TASKS)
    failed_deliveries = value("notification_deliveries", "failed")
    try:
        channels_url = _changelist("admin:push_telegramnotificationchannel_changelist")
    except Exception:
        channels_url = ""
    return [
        {
            "label": "Сбои фоновых задач",
            "value": failures,
            "hint": f"повторы: {retries} · всего с момента сброса Redis",
            "tone": "danger" if failures else "ok",
            "url": "",
        },
        {
            "label": "Неудачные доставки уведомлений",
            "value": failed_deliveries,
            "hint": "канал отключается после трёх сбоев подряд",
            "tone": "warn" if failed_deliveries else "ok",
            "url": channels_url if failed_deliveries else "",
        },
    ]


def build_dashboard() -> list[dict[str, Any]]:
    """One entry per attention area; ``tone`` drives the template colour."""
    new_reports = SourceReport.objects.filter(status=SourceReport.Status.NEW).count()
    reviewing_reports = SourceReport.objects.filter(status=SourceReport.Status.REVIEWING).count()
    provider_errors = Source.objects.filter(availability="provider_error").count()
    episodes_without_date = Episode.objects.filter(air_date__isnull=True).count()
    pending_reviews = TitleReview.objects.filter(status=TitleReview.Status.PENDING).count()
    tiers = _poster_tier_counts()
    below_maximum = tiers["fallback"] + tiers["missing"]
    missing_avatar = Q(image_url="") | Q(image_url__isnull=True) | Q(image_url__icontains="missing_original")
    characters_total = Character.objects.count()
    characters_missing = Character.objects.filter(missing_avatar).count()
    creators_total = Creator.objects.count()
    creators_missing = Creator.objects.filter(missing_avatar).count()
    main_links = TitleCharacter.objects.filter(role__in=("protagonist", "antagonist"))
    main_total = main_links.values("character_id").distinct().count()
    main_missing = main_links.filter(
        Q(character__image_url="")
        | Q(character__image_url__isnull=True)
        | Q(character__image_url__icontains="missing_original")
    ).values("character_id").distinct().count()

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
        {
            "label": "Персонажи без аватара",
            "value": characters_missing,
            "hint": f"из {characters_total} персонажей",
            "tone": "warn" if characters_missing else "ok",
            "url": _changelist("admin:catalog_character_changelist", "avatar=missing"),
        },
        {
            "label": "Главные герои без аватара",
            "value": main_missing,
            "hint": f"из {main_total} уникальных главных героев",
            "tone": "danger" if main_missing else "ok",
            "url": _changelist("admin:catalog_character_changelist", "avatar=missing&importance=main"),
        },
        {
            "label": "Авторы без фото",
            "value": creators_missing,
            "hint": f"из {creators_total} авторов",
            "tone": "warn" if creators_missing else "ok",
            "url": _changelist("admin:catalog_creator_changelist", "avatar=missing"),
        },
        *_system_cards(),
    ]


def staff_index(request: HttpRequest) -> HttpResponse:
    """Shadow of ``admin.site.index`` that adds the summary context."""
    return admin.site.index(
        request,
        extra_context={"dashboard": build_dashboard(), "availability": _availability_section()},
    )


def shadowed_admin_urls() -> tuple[list[Any], str, str]:
    """Default ``/staff/`` urlconf with the index replaced by :func:`staff_index`.

    Everything else — permissions, login flow, audit logging — is the stock
    admin, so existing rights and ModelAdmin behaviour stay exactly as they are.
    """
    patterns, app_namespace, instance_namespace = admin.site.urls
    kept = [pattern for pattern in patterns if getattr(pattern, "name", None) != "index"]
    shadowed = [path("", admin.site.admin_view(staff_index), name="index"), *kept]
    return shadowed, app_namespace, instance_namespace
