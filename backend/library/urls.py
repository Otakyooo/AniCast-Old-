from django.urls import path

from .views import (
    CollectionDetailView,
    CollectionItemDetailView,
    CollectionItemListView,
    CollectionListView,
    EpisodeProgressView,
    HistoryListView,
    LibraryEntryView,
    LibraryListView,
    PublicCollectionDetailView,
    RecommendationListView,
    TitleNoteListView,
    TitleNoteView,
)

urlpatterns = [
    path("collections/", CollectionListView.as_view(), name="collection-list"),
    path("collections/<slug:slug>/", CollectionDetailView.as_view(), name="collection-detail"),
    path("collections/<slug:slug>/items/", CollectionItemListView.as_view(), name="collection-item-list"),
    path(
        "collections/<slug:slug>/items/<slug:title_slug>/",
        CollectionItemDetailView.as_view(),
        name="collection-item-detail",
    ),
    path(
        "public/collections/<uuid:public_id>/<slug:slug>/",
        PublicCollectionDetailView.as_view(),
        name="public-collection-detail",
    ),
    path("library/", LibraryListView.as_view(), name="library-list"),
    path("library/<slug:slug>/", LibraryEntryView.as_view(), name="library-entry"),
    path("history/", HistoryListView.as_view(), name="history-list"),
    path("episodes/<slug:slug>/<int:number>/progress/", EpisodeProgressView.as_view(), name="episode-progress"),
    path("notes/", TitleNoteListView.as_view(), name="title-note-list"),
    path("notes/<slug:slug>/", TitleNoteView.as_view(), name="title-note"),
    path("recommendations/", RecommendationListView.as_view(), name="recommendations"),
]
