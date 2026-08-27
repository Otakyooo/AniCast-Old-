from urllib.parse import urlencode
import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core import signing
from django.db import connection, transaction
from django.db.models import F, Sum
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .metrics import increment
from .models import DailyVisitStat

logger = logging.getLogger("anicast.health")

VISIT_COOKIE = "anicast_visit_day"
VISIT_COOKIE_SALT = "anicast.visit-day.v1"
BOT_USER_AGENT_MARKERS = (
    "bot", "crawler", "spider", "slurp", "bingpreview", "headless", "lighthouse",
    "monitor", "prometheus", "blackbox", "uptime", "curl", "wget", "python-requests",
)


def staff_login_redirect(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("/staff/")
    return redirect(f"/login?{urlencode({'next': '/staff/'})}")


def _visit_summary(day) -> dict[str, int]:
    today = DailyVisitStat.objects.filter(day=day).values_list("visits", flat=True).first() or 0
    total = DailyVisitStat.objects.aggregate(total=Sum("visits"))["total"] or 0
    return {"total": total, "today": today}


def _visit_was_counted(request, day) -> bool:
    value = request.COOKIES.get(VISIT_COOKIE)
    if not value:
        return False
    try:
        return signing.loads(value, salt=VISIT_COOKIE_SALT, max_age=3 * 24 * 60 * 60) == day.isoformat()
    except signing.BadSignature:
        return False


def _is_automated_visit(request) -> bool:
    user_agent = request.headers.get("User-Agent", "").lower()
    return not user_agent or any(marker in user_agent for marker in BOT_USER_AGENT_MARKERS)


@csrf_protect
@require_POST
def record_visit(request):
    """Count at most one browser visit per signed-cookie day without identifiers."""

    day = timezone.localdate()
    counted = False
    if not _is_automated_visit(request) and not _visit_was_counted(request, day):
        with transaction.atomic():
            stat, created = DailyVisitStat.objects.select_for_update().get_or_create(
                day=day, defaults={"visits": 1}
            )
            if not created:
                DailyVisitStat.objects.filter(pk=stat.pk).update(visits=F("visits") + 1)
        counted = True

    response = JsonResponse({**_visit_summary(day), "counted": counted})
    response["Cache-Control"] = "no-store"
    if counted:
        response.set_cookie(
            VISIT_COOKIE,
            signing.dumps(day.isoformat(), salt=VISIT_COOKIE_SALT),
            max_age=2 * 24 * 60 * 60,
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite="Lax",
            path="/",
        )
    return response


@require_GET
def health_live(request):
    return JsonResponse({"status": "ok", "service": "backend"})


@require_GET
def health_ready(request):
    dependencies = {"database": "ok", "cache": "ok"}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as error:
        dependencies["database"] = "unavailable"
        increment("readiness_checks", "database", "failed")
        logger.warning("readiness dependency failed", extra={
            "event": "readiness_check_failed", "dependency": "database", "exception_type": type(error).__name__
        })
    key = f"health-ready:{uuid.uuid4().hex}"
    try:
        cache.set(key, "ok", timeout=10)
        if cache.get(key) != "ok":
            raise RuntimeError("Cache is unavailable")
    except Exception as error:
        dependencies["cache"] = "unavailable"
        increment("readiness_checks", "cache", "failed")
        logger.warning("readiness dependency failed", extra={
            "event": "readiness_check_failed", "dependency": "cache", "exception_type": type(error).__name__
        })
    finally:
        try:
            cache.delete(key)
        except Exception:
            pass
    status = 200 if all(value == "ok" for value in dependencies.values()) else 503
    return JsonResponse({
        "status": "ok" if status == 200 else "unavailable", "service": "backend", "dependencies": dependencies
    }, status=status)
