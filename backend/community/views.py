from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from catalog.models import Title
from catalog.serializers import TitleSerializer
from accounts.models import User
from library.models import TitleCollection, TitleCollectionItem

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


class PublicProfileView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def get(self, request, public_id):
        user = get_object_or_404(User, public_id=public_id, profile_is_public=True, is_active=True)
        collections = list(
            TitleCollection.objects.filter(owner=user, is_public=True)
            .annotate(item_count=Count("items"))
            .order_by("-updated_at", "-id")[:12]
        )
        collection_ids = [collection.id for collection in collections]
        preview_items: dict[int, list[dict]] = {collection_id: [] for collection_id in collection_ids}
        if collection_ids:
            items = (
                TitleCollectionItem.objects.filter(collection_id__in=collection_ids, position__lt=4)
                .select_related("title", "title__franchise")
                .prefetch_related("title__translations", "title__franchise__translations", "title__genres__translations")
                .order_by("collection_id", "position", "id")
            )
            for item in items:
                preview_items[item.collection_id].append(
                    TitleSerializer(item.title, context={"request": request}).data
                )
        reviews = (
            TitleReview.objects.filter(user=user, status=TitleReview.Status.APPROVED)
            .select_related("user", "title")
            .prefetch_related("title__translations")[:10]
        )
        return Response({
            "profile": {
                "public_id": str(user.public_id),
                "display_name": user.display_name,
                "bio": user.bio,
            },
            "stats": {
                "collections": TitleCollection.objects.filter(owner=user, is_public=True).count(),
                "reviews": TitleReview.objects.filter(user=user, status=TitleReview.Status.APPROVED).count(),
            },
            "collections": [
                {
                    "name": collection.name,
                    "slug": collection.slug,
                    "description": collection.description,
                    "item_count": collection.item_count,
                    "preview_titles": preview_items[collection.id],
                    "updated_at": collection.updated_at,
                }
                for collection in collections
            ],
            "reviews": PublicReviewSerializer(reviews, many=True, context={"request": request}).data,
        })


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
