from urllib.parse import urlencode
import logging
import uuid

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

from .metrics import increment

logger = logging.getLogger("anicast.health")


def staff_login_redirect(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("/staff/")
    return redirect(f"/login?{urlencode({'next': '/staff/'})}")


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
