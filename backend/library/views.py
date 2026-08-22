from django.contrib.auth import get_user_model
from django.http import Http404
from django.db import IntegrityError, transaction
from django.db.models import Case, F, FloatField, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Episode, Title
from community.models import TitleRating

from .models import EpisodeProgress, LibraryEntry, TitleCollection, TitleCollectionItem, TitleNote
from .serializers import (
    EpisodeProgressSerializer,
    EpisodeProgressWriteSerializer,
    CollectionItemCreateSerializer,
    CollectionItemMoveSerializer,
    CollectionItemSerializer,
    CollectionSerializer,
    LibraryEntrySerializer,
    LibraryEntryWriteSerializer,
    RecommendationSerializer,
    PublicCollectionSerializer,
    TitleNoteSerializer,
    TitleNoteWriteSerializer,
)

User = get_user_model()


def collection_queryset():
    return TitleCollection.objects.select_related("owner").prefetch_related(
        "items__title__translations",
        "items__title__franchise__translations",
        "items__title__genres__translations",
    )


def reindex_collection_items(collection, ordered_items):
    TitleCollectionItem.objects.filter(collection=collection).update(position=F("position") + 201)
    for position, item in enumerate(ordered_items):
        if item.pk is not None:
            item.position = position
            item.save(update_fields=["position"])


class LibraryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class LibraryListView(ListAPIView):
    serializer_class = LibraryEntrySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LibraryPagination

    def get_queryset(self):
        queryset = LibraryEntry.objects.filter(user=self.request.user).select_related(
            "title", "title__franchise"
        ).prefetch_related("title__genres")
        entry_status = self.request.query_params.get("status", "").strip()
        if entry_status:
            valid_statuses = {choice for choice, _ in LibraryEntry.Status.choices}
            if entry_status not in valid_statuses:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"status": "Неизвестный статус библиотеки."})
            queryset = queryset.filter(status=entry_status)
        favorite = self.request.query_params.get("favorite", "").strip().lower()
        if favorite:
            if favorite not in {"true", "false"}:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"favorite": "Используйте true или false."})
            queryset = queryset.filter(is_favorite=favorite == "true")
        return queryset


class LibraryEntryView(APIView):
    permission_classes = [IsAuthenticated]

    def get_entry(self, request, slug):
        return get_object_or_404(
            LibraryEntry.objects.select_related("title", "title__franchise").prefetch_related("title__genres"),
            user=request.user,
            title__slug=slug,
        )

    def get(self, request, slug):
        return Response(LibraryEntrySerializer(self.get_entry(request, slug)).data)

    def put(self, request, slug):
        title = get_object_or_404(Title, slug=slug)
        serializer = LibraryEntryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry, created = LibraryEntry.objects.update_or_create(
            user=request.user,
            title=title,
            defaults=serializer.validated_data,
        )
        entry = LibraryEntry.objects.select_related("title", "title__franchise").prefetch_related(
            "title__genres"
        ).get(pk=entry.pk)
        return Response(LibraryEntrySerializer(entry).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, slug):
        self.get_entry(request, slug).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class HistoryListView(ListAPIView):
    serializer_class = EpisodeProgressSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LibraryPagination

    def get_queryset(self):
        return EpisodeProgress.objects.filter(user=self.request.user).select_related(
            "episode", "episode__title", "episode__title__franchise"
        ).prefetch_related("episode__sources", "episode__title__genres")


class EpisodeProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get_episode(self, slug, number):
        return get_object_or_404(
            Episode.objects.select_related("title").prefetch_related("sources"),
            title__slug=slug,
            number=number,
        )

    def get_progress(self, request, slug, number):
        return get_object_or_404(
            EpisodeProgress.objects.select_related(
                "episode", "episode__title", "episode__title__franchise"
            ).prefetch_related("episode__sources", "episode__title__genres"),
            user=request.user,
            episode__title__slug=slug,
            episode__number=number,
        )

    def get(self, request, slug, number):
        return Response(EpisodeProgressSerializer(self.get_progress(request, slug, number)).data)

    def post(self, request, slug, number):
        episode = self.get_episode(slug, number)
        progress, created = EpisodeProgress.objects.update_or_create(
            user=request.user,
            episode=episode,
            defaults={"last_opened_at": timezone.now()},
        )
        return Response(
            EpisodeProgressSerializer(progress).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def put(self, request, slug, number):
        serializer = EpisodeProgressWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        episode = self.get_episode(slug, number)
        watched = serializer.validated_data["is_watched"]
        progress, created = EpisodeProgress.objects.get_or_create(
            user=request.user,
            episode=episode,
            defaults={"last_opened_at": timezone.now()},
        )
        progress.is_watched = watched
        progress.watched_at = timezone.now() if watched else None
        progress.save(update_fields=["is_watched", "watched_at", "updated_at"])
        return Response(
            EpisodeProgressSerializer(progress).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TitleNoteListView(ListAPIView):
    serializer_class = TitleNoteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LibraryPagination

    def get_queryset(self):
        return TitleNote.objects.filter(user=self.request.user).select_related(
            "title", "title__franchise"
        ).prefetch_related("title__genres")


class TitleNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get_note(self, request, slug):
        return get_object_or_404(
            TitleNote.objects.select_related("title", "title__franchise").prefetch_related("title__genres"),
            user=request.user,
            title__slug=slug,
        )

    def get(self, request, slug):
        return Response(TitleNoteSerializer(self.get_note(request, slug)).data)

    def put(self, request, slug):
        serializer = TitleNoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = get_object_or_404(Title, slug=slug)
        note, created = TitleNote.objects.update_or_create(
            user=request.user,
            title=title,
            defaults={"body": serializer.validated_data["body"]},
        )
        note = TitleNote.objects.select_related("title", "title__franchise").prefetch_related("title__genres").get(pk=note.pk)
        return Response(TitleNoteSerializer(note).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, slug):
        self.get_note(request, slug).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecommendationListView(ListAPIView):
    serializer_class = RecommendationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LibraryPagination

    library_status_weights: dict[str, float] = {
        LibraryEntry.Status.WATCHING: 1.0,
        LibraryEntry.Status.COMPLETED: 1.0,
        LibraryEntry.Status.ON_HOLD: 0.5,
        LibraryEntry.Status.PLANNED: 0.5,
        LibraryEntry.Status.DROPPED: 0.0,
    }
    rating_genre_weight = 0.5
    watched_genre_weight = 0.5
    franchise_boost = 3.0

    def genre_weights(self):
        weights: dict[int, float] = {}
        entries = (
            LibraryEntry.objects.filter(user=self.request.user)
            .exclude(status=LibraryEntry.Status.DROPPED)
            .prefetch_related("title__genres")
        )
        for entry in entries:
            weight = self.library_status_weights.get(entry.status, 0.0)
            for genre in entry.title.genres.all():
                weights[genre.id] = weights.get(genre.id, 0.0) + weight
        high_ratings = TitleRating.objects.filter(user=self.request.user, value__gte=8).prefetch_related(
            "title__genres"
        )
        for rating in high_ratings:
            for genre in rating.title.genres.all():
                weights[genre.id] = weights.get(genre.id, 0.0) + self.rating_genre_weight
        watched_title_ids = list(
            EpisodeProgress.objects.filter(user=self.request.user, is_watched=True).values_list(
                "episode__title_id", flat=True
            )
        )
        watched_titles = Title.objects.filter(id__in=watched_title_ids).prefetch_related("genres")
        for title in watched_titles:
            for genre in title.genres.all():
                weights[genre.id] = weights.get(genre.id, 0.0) + self.watched_genre_weight
        return weights

    def get_queryset(self):
        user = self.request.user
        library_title_ids = list(
            LibraryEntry.objects.filter(user=user).values_list("title_id", flat=True)
        )
        queryset = Title.objects.exclude(id__in=library_title_ids).select_related("franchise").prefetch_related(
            "translations", "franchise__translations", "genres", "genres__translations"
        )
        weights = self.genre_weights()
        if not weights:
            return queryset.annotate(score=Value(0.0, output_field=FloatField())).order_by(
                F("year").desc(nulls_last=True), "name", "slug"
            )
        franchise_ids = {
            franchise_id
            for franchise_id in LibraryEntry.objects.filter(user=user)
            .exclude(status=LibraryEntry.Status.DROPPED)
            .values_list("title__franchise_id", flat=True)
            if franchise_id is not None
        }
        genre_whens = [When(genres__id=genre_id, then=Value(weight)) for genre_id, weight in weights.items()]
        score: object = Coalesce(
            Sum(Case(*genre_whens, default=Value(0.0), output_field=FloatField()), output_field=FloatField()),
            Value(0.0),
            output_field=FloatField(),
        )
        if franchise_ids:
            score = score + Case(
                When(franchise_id__in=franchise_ids, then=Value(self.franchise_boost)),
                default=Value(0.0),
                output_field=FloatField(),
            )
        return (
            queryset.filter(genres__id__in=weights.keys())
            .annotate(score=score)
            .distinct()
            .order_by("-score", F("year").desc(nulls_last=True), "name", "slug")
        )


class CollectionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        collections = collection_queryset().filter(owner=request.user)
        return Response(CollectionSerializer(collections, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = CollectionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            if TitleCollection.objects.filter(owner=request.user).count() >= 50:
                raise ValidationError({"detail": "Достигнут лимит в 50 коллекций."})
            try:
                collection = serializer.save(owner=request.user)
            except IntegrityError as exc:
                raise ValidationError({"slug": "Коллекция с таким slug уже существует."}) from exc
        collection = collection_queryset().get(pk=collection.pk)
        return Response(
            CollectionSerializer(collection, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CollectionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, slug):
        return get_object_or_404(collection_queryset(), owner=request.user, slug=slug)

    def get(self, request, slug):
        return Response(CollectionSerializer(self.get_object(request, slug), context={"request": request}).data)

    def patch(self, request, slug):
        collection = self.get_object(request, slug)
        serializer = CollectionSerializer(collection, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError as exc:
            raise ValidationError({"slug": "Коллекция с таким slug уже существует."}) from exc
        return Response(serializer.data)

    def put(self, request, slug):
        collection = self.get_object(request, slug)
        serializer = CollectionSerializer(collection, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, slug):
        self.get_object(request, slug).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CollectionItemListView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        serializer = CollectionItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = get_object_or_404(Title, slug=serializer.validated_data["title_slug"])
        with transaction.atomic():
            collection = get_object_or_404(
                TitleCollection.objects.select_for_update(), owner=request.user, slug=slug
            )
            items = list(
                TitleCollectionItem.objects.select_for_update()
                .filter(collection=collection)
                .order_by("position", "id")
            )
            if len(items) >= 200:
                raise ValidationError({"detail": "Достигнут лимит в 200 элементов."})
            if any(item.title_id == title.id for item in items):
                raise ValidationError({"title_slug": "Тайтл уже добавлен в коллекцию."})
            position = serializer.validated_data.get("position", len(items))
            if position > len(items):
                raise ValidationError({"position": "Позиция выходит за границы коллекции."})
            reindex_collection_items(collection, items)
            TitleCollectionItem.objects.filter(collection=collection, position__gte=position).update(
                position=F("position") + 201
            )
            shifted = list(TitleCollectionItem.objects.filter(collection=collection).order_by("position", "id"))
            for index, item in enumerate(shifted):
                item.position = index if index < position else index + 1
                item.save(update_fields=["position"])
            item = TitleCollectionItem.objects.create(collection=collection, title=title, position=position)
            collection.save(update_fields=["updated_at"])
        item = TitleCollectionItem.objects.select_related("title", "title__franchise").prefetch_related(
            "title__translations", "title__franchise__translations", "title__genres__translations"
        ).get(pk=item.pk)
        return Response(
            CollectionItemSerializer(item, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CollectionItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug, title_slug):
        serializer = CollectionItemMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            collection = get_object_or_404(
                TitleCollection.objects.select_for_update(), owner=request.user, slug=slug
            )
            items = list(
                TitleCollectionItem.objects.select_for_update()
                .filter(collection=collection)
                .select_related("title")
                .order_by("position", "id")
            )
            item = next((candidate for candidate in items if candidate.title.slug == title_slug), None)
            if item is None:
                raise Http404
            position = serializer.validated_data["position"]
            if position >= len(items):
                raise ValidationError({"position": "Позиция выходит за границы коллекции."})
            items.remove(item)
            items.insert(position, item)
            reindex_collection_items(collection, items)
            collection.save(update_fields=["updated_at"])
        item = TitleCollectionItem.objects.select_related("title", "title__franchise").prefetch_related(
            "title__translations", "title__franchise__translations", "title__genres__translations"
        ).get(pk=item.pk)
        return Response(CollectionItemSerializer(item, context={"request": request}).data)

    def delete(self, request, slug, title_slug):
        with transaction.atomic():
            collection = get_object_or_404(
                TitleCollection.objects.select_for_update(), owner=request.user, slug=slug
            )
            items = list(
                TitleCollectionItem.objects.select_for_update()
                .filter(collection=collection)
                .select_related("title")
                .order_by("position", "id")
            )
            item = next((candidate for candidate in items if candidate.title.slug == title_slug), None)
            if item is None:
                raise Http404
            items.remove(item)
            item.delete()
            reindex_collection_items(collection, items)
            collection.save(update_fields=["updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicCollectionDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type[BaseAuthentication]] = []

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def get(self, request, public_id, slug):
        collection = get_object_or_404(
            collection_queryset(), owner__public_id=public_id, slug=slug, is_public=True
        )
        return Response(PublicCollectionSerializer(collection, context={"request": request}).data)
