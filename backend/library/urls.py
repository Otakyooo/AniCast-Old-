from django.urls import path

from .views import (
    EpisodeProgressView,
    HistoryListView,
    LibraryEntryView,
    LibraryListView,
    RecommendationListView,
    TitleNoteListView,
    TitleNoteView,
)

urlpatterns = [
    path("library/", LibraryListView.as_view(), name="library-list"),
    path("library/<slug:slug>/", LibraryEntryView.as_view(), name="library-entry"),
    path("history/", HistoryListView.as_view(), name="history-list"),
    path("episodes/<slug:slug>/<int:number>/progress/", EpisodeProgressView.as_view(), name="episode-progress"),
    path("notes/", TitleNoteListView.as_view(), name="title-note-list"),
    path("notes/<slug:slug>/", TitleNoteView.as_view(), name="title-note"),
    path("recommendations/", RecommendationListView.as_view(), name="recommendations"),
]
