from django.urls import path

from .views import EpisodeProgressView, HistoryListView, LibraryEntryView, LibraryListView

urlpatterns = [
    path("library/", LibraryListView.as_view(), name="library-list"),
    path("library/<slug:slug>/", LibraryEntryView.as_view(), name="library-entry"),
    path("history/", HistoryListView.as_view(), name="history-list"),
    path("episodes/<slug:slug>/<int:number>/progress/", EpisodeProgressView.as_view(), name="episode-progress"),
]
