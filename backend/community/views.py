from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework.authentication import BaseAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from common.throttling import LiveRatesMixin

from catalog.models import Title
from catalog.serializers import TitleSerializer
from accounts.models import User
from library.models import TitleCollection, TitleCollectionItem

from .models import ProfileFollow, TitleRating, TitleReview
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


def published_reviews():
    """Approved reviews whose author is still an active account.

    Deactivating a user is the project's takedown mechanism, and it already hides
    the profile (`PublicProfileView`) and blocks following. Without the same
    filter here a deactivated author's reviews stayed readable on every title
    page, so the takedown was partial.
    """
    return TitleReview.objects.filter(
        status=TitleReview.Status.APPROVED, user__is_active=True
    ).select_related("user", "title").prefetch_related("title__translations")


class CommunitySummaryView(APIView):
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        # The payload mixes public aggregates with the viewer's own rating and
        # review, so it must never sit in a shared cache.
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response

    def get(self, request, slug):
        title = get_object_or_404(Title, slug=slug)
        active = TitleRating.objects.filter(title=title, user__is_active=True)
        rating = active.aggregate(average=Avg("value"))
        reviews = published_reviews().filter(title=title)[:20]
        own_rating = own_review = None
        if request.user.is_authenticated:
            own_rating = TitleRating.objects.filter(title=title, user=request.user).first()
            own_review = TitleReview.objects.filter(title=title, user=request.user).select_related("user", "title").first()
        return Response({
            "average_rating": round(rating["average"], 2) if rating["average"] is not None else None,
            "rating_count": active.count(),
            "reviews": PublicReviewSerializer(reviews, many=True, context={"request": request}).data,
            "my_rating": RatingSerializer(own_rating).data if own_rating else None,
            "my_review": PrivateReviewSerializer(own_review, context={"request": request}).data if own_review else None,
        })


class PublicReviewListView(ListAPIView):
    serializer_class = PublicReviewSerializer
    permission_classes = [AllowAny]
    pagination_class = CommunityPagination

    def get_queryset(self):
        queryset = published_reviews()
        if slug := self.request.query_params.get("title", "").strip():
            queryset = queryset.filter(title__slug=slug)
        return queryset


class PublicProfileView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type[BaseAuthentication]] = []

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
                "followers": ProfileFollow.objects.filter(following=user).count(),
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


class FollowThrottle(LiveRatesMixin, UserRateThrottle):
    scope = "follow"


class PrivateNoStoreAPIView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response


class ProfileFollowView(PrivateNoStoreAPIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FollowThrottle]

    def get_throttles(self):
        return [] if self.request.method == "GET" else super().get_throttles()

    def target(self, public_id):
        return get_object_or_404(User, public_id=public_id, profile_is_public=True, is_active=True)

    def payload(self, request, target):
        return {
            "is_self": request.user.pk == target.pk,
            "is_following": ProfileFollow.objects.filter(follower=request.user, following=target).exists(),
            "followers": ProfileFollow.objects.filter(following=target).count(),
        }

    def get(self, request, public_id):
        target = self.target(public_id)
        return Response(self.payload(request, target))

    def put(self, request, public_id):
        target = self.target(public_id)
        if request.user.pk == target.pk:
            raise ValidationError({"detail": "Нельзя подписаться на собственный профиль."})
        _, created = ProfileFollow.objects.get_or_create(follower=request.user, following=target)
        return Response(self.payload(request, target), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, public_id):
        target = self.target(public_id)
        ProfileFollow.objects.filter(follower=request.user, following=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowingFeedView(PrivateNoStoreAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        following_ids = ProfileFollow.objects.filter(
            follower=request.user,
            following__profile_is_public=True,
            following__is_active=True,
        ).values_list("following_id", flat=True)
        reviews = list(
            TitleReview.objects.filter(
                user_id__in=following_ids,
                user__profile_is_public=True,
                status=TitleReview.Status.APPROVED,
            ).select_related("user", "title").prefetch_related("title__translations")[:30]
        )
        collections = list(
            TitleCollection.objects.filter(
                owner_id__in=following_ids,
                owner__profile_is_public=True,
                is_public=True,
            ).select_related("owner").annotate(item_count=Count("items")).order_by("-updated_at", "-id")[:30]
        )
        review_data = PublicReviewSerializer(reviews, many=True, context={"request": request}).data
        items = [
            {
                "kind": "review",
                "occurred_at": review.published_at or review.updated_at,
                "author": {"public_id": str(review.user.public_id), "display_name": review.user.display_name},
                "review": serialized,
            }
            for review, serialized in zip(reviews, review_data, strict=True)
        ]
        items += [
            {
                "kind": "collection",
                "occurred_at": collection.updated_at,
                "author": {"public_id": str(collection.owner.public_id), "display_name": collection.owner.display_name},
                "collection": {
                    "name": collection.name,
                    "slug": collection.slug,
                    "description": collection.description,
                    "item_count": collection.item_count,
                },
            }
            for collection in collections
        ]
        items.sort(key=lambda item: item["occurred_at"], reverse=True)
        return Response({"count": len(items[:30]), "results": items[:30]})


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


class ReviewThrottle(LiveRatesMixin, UserRateThrottle):
    scope = "review"


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
