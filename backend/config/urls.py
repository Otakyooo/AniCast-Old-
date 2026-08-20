from django.urls import path
from common.views import health_live, health_ready

urlpatterns = [
    path("health/live", health_live, name="health-live"),
    path("health/ready", health_ready, name="health-ready"),
]
