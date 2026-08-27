from django.contrib import admin
from django.urls import include, path
from common.staff_dashboard import shadowed_admin_urls
from common.views import health_live, health_ready, record_visit, staff_login_redirect
from common.metrics import metrics_view

admin.site.site_header = "AniCast — управление контентом"
admin.site.site_title = "AniCast Staff"
admin.site.index_title = "Контент и аудит"
# Editor dashboard on top of the stock index (functional concept §16).
admin.site.index_template = "staff/index.html"

urlpatterns = [
    path("health/live", health_live, name="health-live"),
    path("health/ready", health_ready, name="health-ready"),
    path("internal/metrics", metrics_view, name="internal-metrics"),
    path("api/v1/analytics/visit/", record_visit, name="record-visit"),
    path("staff/login/", staff_login_redirect, name="staff-login"),
    path("staff/", shadowed_admin_urls()),
    path("api/v1/", include("catalog.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("library.urls")),
    path("api/v1/", include("push.urls")),
    path("api/v1/", include("community.urls")),
]
