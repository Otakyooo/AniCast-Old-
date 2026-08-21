from django.urls import path

from .views import (
    CharacterDetailView,
    CharacterListView,
    FranchiseDetailView,
    FranchiseListView,
    MediaAssetListView,
    PlaybackView,
    ScheduleView,
    SourceReportView,
    TitleDetailView,
    TitleListView,
)

urlpatterns = [
    path("titles/", TitleListView.as_view(), name="title-list"),
    path("titles/<slug:slug>/", TitleDetailView.as_view(), name="title-detail"),
    path("schedule/", ScheduleView.as_view(), name="schedule"),
    path("source-reports/", SourceReportView.as_view(), name="source-report-list"),
    path("sources/<int:source_id>/playback/", PlaybackView.as_view(), name="source-playback"),
    path("franchises/", FranchiseListView.as_view(), name="franchise-list"),
    path("franchises/<slug:slug>/", FranchiseDetailView.as_view(), name="franchise-detail"),
    path("characters/", CharacterListView.as_view(), name="character-list"),
    path("characters/<slug:slug>/", CharacterDetailView.as_view(), name="character-detail"),
    path("media/", MediaAssetListView.as_view(), name="media-list"),
]
