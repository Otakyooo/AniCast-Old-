from django.urls import path

from .views import ScheduleView, SourceReportView, TitleDetailView, TitleListView

urlpatterns = [
    path("titles/", TitleListView.as_view(), name="title-list"),
    path("titles/<slug:slug>/", TitleDetailView.as_view(), name="title-detail"),
    path("schedule/", ScheduleView.as_view(), name="schedule"),
    path("source-reports/", SourceReportView.as_view(), name="source-report-list"),
]
