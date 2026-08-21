from django.contrib import admin
from django.urls import include, path
from common.views import health_live, health_ready, staff_login_redirect

admin.site.site_header = "AniCast — управление контентом"
admin.site.site_title = "AniCast Staff"
admin.site.index_title = "Контент и аудит"

urlpatterns = [
    path("health/live", health_live, name="health-live"),
    path("health/ready", health_ready, name="health-ready"),
    path("staff/login/", staff_login_redirect, name="staff-login"),
    path("staff/", admin.site.urls),
    path("api/v1/", include("catalog.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("library.urls")),
    path("api/v1/", include("push.urls")),
]
