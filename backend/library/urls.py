from django.urls import path

from .views import LibraryEntryView, LibraryListView

urlpatterns = [
    path("library/", LibraryListView.as_view(), name="library-list"),
    path("library/<slug:slug>/", LibraryEntryView.as_view(), name="library-entry"),
]
