from django.db import connection
from rest_framework.response import Response
from rest_framework.status import HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


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
    except Exception:
        return Response({"status": "unavailable", "service": "backend"}, status=HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"status": "ok", "service": "backend", "dependencies": {"database": "ok"}})
