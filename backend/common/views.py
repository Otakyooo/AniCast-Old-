from urllib.parse import urlencode

from django.db import connection
from django.core.cache import cache
from django.shortcuts import redirect
from rest_framework.response import Response
from rest_framework.status import HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


def staff_login_redirect(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("/staff/")
    return redirect(f"/login?{urlencode({'next': '/staff/'})}")


@api_view(["GET"])
@permission_classes([AllowAny])
def health_live(request):
    return Response({"status": "ok", "service": "backend"})


@api_view(["GET"])
@permission_classes([AllowAny])
def health_ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        cache.set("health-ready", "ok", timeout=10)
        if cache.get("health-ready") != "ok":
            raise RuntimeError("Cache is unavailable")
    except Exception:
        return Response({"status": "unavailable", "service": "backend"}, status=HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"status": "ok", "service": "backend", "dependencies": {"database": "ok", "cache": "ok"}})
