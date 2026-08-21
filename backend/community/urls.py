from django.urls import path

from .views import CommunitySummaryView, PublicReviewListView, RatingView, ReviewView

urlpatterns = [
    path("titles/<slug:slug>/community/", CommunitySummaryView.as_view(), name="community-summary"),
    path("community/reviews/", PublicReviewListView.as_view(), name="public-reviews"),
    path("community/ratings/<slug:slug>/", RatingView.as_view(), name="rating"),
    path("community/reviews/<slug:slug>/", ReviewView.as_view(), name="review"),
]
