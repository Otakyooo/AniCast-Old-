from django.urls import path
from common.views import health_live, health_ready

from django.urls import include

urlpatterns = [
    path("health/live", health_live, name="health-live"),
    path("health/ready", health_ready, name="health-ready"),
    path("api/v1/", include("catalog.urls")),
]
