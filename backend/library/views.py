from django.contrib.auth import get_user_model
from django.http import Http404
from django.db import IntegrityError, transaction
from django.db.models import Avg, Case, Count, F, FloatField, IntegerField, Min, OuterRef, Q, Subquery, Sum, Value, When
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

from catalog.i18n import translated_value
from catalog.models import Episode, Genre, Title
from catalog.playback import playback_sources_prefetch
from catalog.serializers import ShelfEpisodeSerializer, TitleSerializer
from community.models import TitleRating

from .models import (
    EpisodeProgress,
    LibraryEntry,
    RecommendationDismissal,
    TitleCollection,
    TitleCollectionItem,
    TitleNote,
)
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
        ).prefetch_related(
            playback_sources_prefetch("episode__sources"),
            "episode__title__genres",
        )


class EpisodeProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get_episode(self, slug, number):
        return get_object_or_404(
            Episode.objects.select_related("title").prefetch_related(playback_sources_prefetch()),
            title__slug=slug,
            number=number,
        )

    def get_progress(self, request, slug, number):
        return get_object_or_404(
            EpisodeProgress.objects.select_related(
                "episode", "episode__title", "episode__title__franchise"
            ).prefetch_related(
                playback_sources_prefetch("episode__sources"),
                "episode__title__genres",
            ),
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


class ContinueWatchingView(APIView):
    """Resume shelf for the home page.

    Built only from recorded progress: the newest opened episode per title plus
    the next existing episode after the highest episode the viewer actually
    marked as watched. Nothing is inferred for titles without progress.
    """

    permission_classes = [IsAuthenticated]
    title_limit = 12

    def get(self, request):
        progress_entries = list(
            EpisodeProgress.objects.filter(user=request.user)
            .select_related("episode", "episode__title", "episode__title__franchise")
            .prefetch_related(
                "episode__translations",
                "episode__title__translations",
                "episode__title__franchise__translations",
                "episode__title__genres",
                "episode__title__genres__translations",
            )
            .order_by("-last_opened_at", "-id")[: self.title_limit * 20]
        )
        latest_by_title: dict[int, EpisodeProgress] = {}
        watched_numbers: dict[int, int] = {}
        for entry in progress_entries:
            title_id = entry.episode.title_id
            if title_id not in latest_by_title and len(latest_by_title) < self.title_limit:
                latest_by_title[title_id] = entry
            if title_id in latest_by_title and entry.is_watched:
                watched_numbers[title_id] = max(watched_numbers.get(title_id, 0), entry.episode.number)
        if not latest_by_title:
            return Response([])
        # An opened-but-unwatched episode resumes on itself; a watched one resumes
        # on the next existing episode, so nothing is skipped or invented.
        resume_after = {
            title_id: watched_numbers.get(title_id, entry.episode.number - 1)
            for title_id, entry in latest_by_title.items()
        }
        candidate_filter = Q()
        for title_id, threshold in resume_after.items():
            candidate_filter |= Q(title_id=title_id, number__gt=threshold)
        # Two bounded queries instead of loading every episode of a long series.
        next_numbers = (
            Episode.objects.filter(candidate_filter)
            .values("title_id")
            .annotate(next_number=Min("number"))
        )
        next_filter = Q()
        for row in next_numbers:
            next_filter |= Q(title_id=row["title_id"], number=row["next_number"])
        next_by_title: dict[int, Episode] = {}
        if next_filter:
            for episode in Episode.objects.filter(next_filter).prefetch_related("translations"):
                next_by_title[episode.title_id] = episode
        context = {"request": request}
        ordered = sorted(latest_by_title.values(), key=lambda entry: entry.last_opened_at, reverse=True)
        return Response([
            {
                "title": TitleSerializer(entry.episode.title, context=context).data,
                "last_episode": ShelfEpisodeSerializer(entry.episode, context=context).data,
                "next_episode": (
                    ShelfEpisodeSerializer(next_by_title[entry.episode.title_id], context=context).data
                    if entry.episode.title_id in next_by_title
                    else None
                ),
                "is_watched": entry.is_watched,
                "watched_count": watched_numbers.get(entry.episode.title_id, 0),
                "last_opened_at": entry.last_opened_at,
            }
            for entry in ordered
        ])


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


def rating_subquery_annotations() -> dict[str, Subquery]:
    """Community rating aggregates as correlated subqueries.

    The recommendation queryset joins genres for scoring, so join-based
    aggregates (catalog's annotate_rating_aggregates) would multiply the
    score sum by the rating count; subqueries keep both independent.
    """

    stats = TitleRating.objects.filter(title=OuterRef("pk")).values("title")
    return {
        "rating_count": Subquery(
            stats.annotate(total=Count("pk")).values("total")[:1], output_field=IntegerField()
        ),
        "rating_avg": Subquery(
            stats.annotate(average=Avg("value")).values("average")[:1], output_field=FloatField()
        ),
    }


class RecommendationListView(ListAPIView):
    serializer_class = RecommendationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LibraryPagination

    library_status_weights: dict[str, float] = {
        LibraryEntry.Status.WATCHING: 1.0,
        LibraryEntry.Status.COMPLETED: 1.0,
        LibraryEntry.Status.ON_HOLD: 0.5,
        LibraryEntry.Status.PLANNED: 0.5,
        # Dropped entries actively push their genres away instead of being
        # ignored; mixed titles can still surface on their positive genres.
        LibraryEntry.Status.DROPPED: -1.0,
    }
    liked_rating_threshold = 8
    disliked_rating_threshold = 4
    rating_genre_weight = 0.5
    watched_genre_weight = 0.5
    franchise_boost_per_entry = 1.5
    franchise_engagement_cap = 4
    reason_genre_limit = 3
    _signals_cache: tuple[dict[int, float], dict[int, int]] | None = None

    def _signals(self) -> tuple[dict[int, float], dict[int, int]]:
        """Genre weights plus per-franchise engagement from real user data."""
        if self._signals_cache is None:
            weights: dict[int, float] = {}
            entries = (
                LibraryEntry.objects.filter(user=self.request.user).prefetch_related("title__genres")
            )
            for entry in entries:
                weight = self.library_status_weights.get(entry.status, 0.0)
                if weight == 0.0:
                    continue
                for genre in entry.title.genres.all():
                    weights[genre.id] = weights.get(genre.id, 0.0) + weight
            liked = TitleRating.objects.filter(
                user=self.request.user, value__gte=self.liked_rating_threshold
            ).prefetch_related("title__genres")
            for rating in liked:
                for genre in rating.title.genres.all():
                    weights[genre.id] = weights.get(genre.id, 0.0) + self.rating_genre_weight
            disliked = TitleRating.objects.filter(
                user=self.request.user, value__lte=self.disliked_rating_threshold
            ).prefetch_related("title__genres")
            for rating in disliked:
                for genre in rating.title.genres.all():
                    weights[genre.id] = weights.get(genre.id, 0.0) - self.rating_genre_weight
            watched_title_ids = list(
                EpisodeProgress.objects.filter(user=self.request.user, is_watched=True).values_list(
                    "episode__title_id", flat=True
                )
            )
            watched_titles = Title.objects.filter(id__in=watched_title_ids).prefetch_related("genres")
            for title in watched_titles:
                for genre in title.genres.all():
                    weights[genre.id] = weights.get(genre.id, 0.0) + self.watched_genre_weight
            engagement: dict[int, int] = {}
            for franchise_id in (
                LibraryEntry.objects.filter(user=self.request.user)
                .exclude(status=LibraryEntry.Status.DROPPED)
                .values_list("title__franchise_id", flat=True)
            ):
                if franchise_id is not None:
                    engagement[franchise_id] = engagement.get(franchise_id, 0) + 1
            self._signals_cache = (weights, engagement)
        return self._signals_cache

    def _fully_watched_title_ids(self) -> set[int]:
        """Titles whose every existing episode the viewer marked watched.

        Bounded to the user's own progress titles, so long-running series
        stay cheap; such titles belong to Continue Watching, not here.
        """
        progress_counts = (
            EpisodeProgress.objects.filter(user=self.request.user, is_watched=True)
            .values("episode__title_id")
            .annotate(watched=Count("id"))
        )
        watched_by_title = {row["episode__title_id"]: row["watched"] for row in progress_counts}
        if not watched_by_title:
            return set()
        episode_counts = (
            Episode.objects.filter(title_id__in=watched_by_title).values("title_id").annotate(total=Count("id"))
        )
        return {
            row["title_id"] for row in episode_counts if watched_by_title[row["title_id"]] >= row["total"]
        }

    def get_queryset(self):
        user = self.request.user
        excluded_ids = (
            set(LibraryEntry.objects.filter(user=user).values_list("title_id", flat=True))
            | self._fully_watched_title_ids()
            | set(RecommendationDismissal.objects.filter(user=user).values_list("title_id", flat=True))
        )
        queryset = Title.objects.exclude(id__in=excluded_ids).select_related("franchise").prefetch_related(
            "translations", "franchise__translations", "genres", "genres__translations"
        )
        weights, engagement = self._signals()
        positive_genres = [genre_id for genre_id, weight in sorted(weights.items()) if weight > 0]
        if not positive_genres:
            # Cold start or only negative signals: an honest recency fallback.
            return queryset.annotate(score=Value(0.0, output_field=FloatField())).order_by(
                F("year").desc(nulls_last=True), "name", "slug"
            )
        # Candidacy stays a subquery so the scoring join below sees every genre
        # of a title and negative weights reach the sum without WHERE filtering.
        candidates = Title.objects.filter(genres__id__in=positive_genres).values("id")
        genre_whens = [
            When(genres__id=genre_id, then=Value(weight))
            for genre_id, weight in sorted(weights.items())
        ]
        score: object = Coalesce(
            Sum(Case(*genre_whens, default=Value(0.0), output_field=FloatField()), output_field=FloatField()),
            Value(0.0),
            output_field=FloatField(),
        )
        if engagement:
            franchise_whens = [
                When(
                    franchise_id=franchise_id,
                    then=Value(min(count, self.franchise_engagement_cap) * self.franchise_boost_per_entry),
                )
                for franchise_id, count in sorted(engagement.items())
            ]
            score = score + Case(*franchise_whens, default=Value(0.0), output_field=FloatField())
        return (
            queryset.filter(id__in=Subquery(candidates))
            .annotate(**rating_subquery_annotations(), score=score)
            .order_by(
                "-score",
                F("rating_avg").desc(nulls_last=True),
                F("year").desc(nulls_last=True),
                "name",
                "slug",
            )
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        weights, engagement = self._signals()
        ordered_genres: list[tuple[int, str]] = []
        positive_ids = [genre_id for genre_id, weight in sorted(weights.items(), key=lambda item: -item[1]) if weight > 0]
        if positive_ids:
            localized = Genre.objects.filter(id__in=positive_ids).prefetch_related("translations")
            names = {genre.id: translated_value(genre, "name", {"request": self.request}) for genre in localized}
            ordered_genres = [(genre_id, names[genre_id]) for genre_id in positive_ids if genre_id in names]
        context.update(
            recommendation_genre_names=ordered_genres,
            recommendation_franchise_ids=set(engagement),
            recommendation_genre_limit=self.reason_genre_limit,
        )
        return context


class RecommendationDismissalView(APIView):
    """Explicit opt-out from personal recommendations; undo restores them."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        title = get_object_or_404(Title, slug=slug)
        _, created = RecommendationDismissal.objects.get_or_create(user=request.user, title=title)
        return Response(status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, slug):
        deleted, _ = RecommendationDismissal.objects.filter(user=request.user, title__slug=slug).delete()
        if not deleted:
            raise Http404
        return Response(status=status.HTTP_204_NO_CONTENT)


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
