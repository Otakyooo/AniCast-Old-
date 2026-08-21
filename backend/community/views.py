from django.db.models import Avg
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from catalog.models import Title

from .models import TitleRating, TitleReview
from .serializers import (
    PrivateReviewSerializer,
    PublicReviewSerializer,
    RatingSerializer,
    RatingWriteSerializer,
    ReviewWriteSerializer,
)


class CommunityPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class CommunitySummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        title = get_object_or_404(Title, slug=slug)
        rating = TitleRating.objects.filter(title=title).aggregate(average=Avg("value"))
        reviews = TitleReview.objects.filter(title=title, status=TitleReview.Status.APPROVED).select_related(
            "user", "title"
        ).prefetch_related("title__translations")[:20]
        own_rating = own_review = None
        if request.user.is_authenticated:
            own_rating = TitleRating.objects.filter(title=title, user=request.user).first()
            own_review = TitleReview.objects.filter(title=title, user=request.user).select_related("user", "title").first()
        return Response({
            "average_rating": round(rating["average"], 2) if rating["average"] is not None else None,
            "rating_count": TitleRating.objects.filter(title=title).count(),
            "reviews": PublicReviewSerializer(reviews, many=True, context={"request": request}).data,
            "my_rating": RatingSerializer(own_rating).data if own_rating else None,
            "my_review": PrivateReviewSerializer(own_review, context={"request": request}).data if own_review else None,
        })


class PublicReviewListView(ListAPIView):
    serializer_class = PublicReviewSerializer
    permission_classes = [AllowAny]
    pagination_class = CommunityPagination

    def get_queryset(self):
        queryset = TitleReview.objects.filter(status=TitleReview.Status.APPROVED).select_related(
            "user", "title"
        ).prefetch_related("title__translations")
        if slug := self.request.query_params.get("title", "").strip():
            queryset = queryset.filter(title__slug=slug)
        return queryset


class RatingView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, slug):
        serializer = RatingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = get_object_or_404(Title, slug=slug)
        rating, created = TitleRating.objects.update_or_create(
            user=request.user, title=title, defaults={"value": serializer.validated_data["value"]}
        )
        return Response(RatingSerializer(rating).data, status=201 if created else 200)

    def delete(self, request, slug):
        rating = get_object_or_404(TitleRating, user=request.user, title__slug=slug)
        rating.delete()
        return Response(status=204)


class ReviewThrottle(UserRateThrottle):
    rate = "5/hour"


class ReviewView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReviewThrottle]

    def get_throttles(self):
        return [] if self.request.method == "GET" else super().get_throttles()

    def get(self, request, slug):
        review = get_object_or_404(TitleReview.objects.select_related("user", "title"), user=request.user, title__slug=slug)
        return Response(PrivateReviewSerializer(review, context={"request": request}).data)

    def put(self, request, slug):
        serializer = ReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = get_object_or_404(Title, slug=slug)
        review, created = TitleReview.objects.update_or_create(
            user=request.user,
            title=title,
            defaults={
                **serializer.validated_data,
                "status": TitleReview.Status.PENDING,
                "moderation_note": "",
                "moderated_by": None,
                "moderated_at": None,
                "published_at": None,
            },
        )
        return Response(PrivateReviewSerializer(review, context={"request": request}).data, status=201 if created else 200)

    def delete(self, request, slug):
        review = get_object_or_404(TitleReview, user=request.user, title__slug=slug)
        review.delete()
        return Response(status=204)
