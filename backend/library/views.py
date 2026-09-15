from django.contrib.auth import get_user_model
from django.http import Http404
from django.db import IntegrityError, transaction
from django.db.models import (
    Avg,
    Case,
    Count,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
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

from catalog import posters
from catalog.i18n import translated_value
from catalog.models import Episode, Genre, Title
from catalog.playback import playback_available, playback_source_queryset, playback_sources_prefetch
from catalog.serializers import (
    ShelfEpisodeSerializer,
    TitleSerializer,
    episode_payload_prefetch,
    title_payload_prefetch,
)
from community.models import TitleRating

from .models import (
    ContinueWatchingHidden,
    EpisodeProgress,
    LibraryEntry,
    RecommendationDismissal,
    TitleCollection,
    TitleCollectionItem,
    TitleNote,
)
from .serializers import (
    EpisodePlaybackProgressSerializer,
    EpisodePlaybackProgressWriteSerializer,
    EpisodeProgressSerializer,
    EpisodeProgressWriteSerializer,
    EpisodeSourceSelectionSerializer,
    CollectionItemCreateSerializer,
    CollectionItemMoveSerializer,
    CollectionItemSerializer,
    CollectionSerializer,
    CollectionSummarySerializer,
    LibraryEntrySerializer,
    LibraryEntryWriteSerializer,
    RecommendationSerializer,
    PublicCollectionSerializer,
    TitleNoteSerializer,
    TitleNoteWriteSerializer,
)

User = get_user_model()


def collection_queryset():
    """Full collection payload for detail endpoints (owner view and public page).

    Detail responses legitimately render every title as a card, and a collection
    is capped at 200 items, so the nested title payload is bounded here. The
    list endpoint must not use this: see :func:`collection_summary_queryset`.
    """
    return TitleCollection.objects.select_related("owner").prefetch_related(
        "items__title__translations",
        "items__title__franchise__translations",
        "items__title__genres__translations",
    )


COLLECTION_PREVIEW_LIMIT = 4


def collection_summary_queryset(preview_limit: int = COLLECTION_PREVIEW_LIMIT):
    """Collection cards: a count plus a handful of posters, nothing more.

    The list endpoint previously reused the detail queryset, so a viewer at both
    ceilings (50 collections × 200 items) received 10 000 nested title payloads
    to draw at most a few posters per card. The count is annotated and the
    preview is selected by position rather than by slicing: a sliced ``Prefetch``
    is executed per parent row, while ``position__lt`` is one query for the whole
    page. Positions are dense from 0 — the unique constraint plus
    :func:`reindex_collection_items` maintain that — so the filter returns
    exactly the first items of each collection.
    """
    preview = (
        TitleCollectionItem.objects.select_related("title")
        .filter(position__lt=preview_limit)
        .order_by("position", "id")
        .prefetch_related("title__translations")
    )
    return (
        TitleCollection.objects.select_related("owner")
        .annotate(item_count=Count("items"))
        .prefetch_related(Prefetch("items", queryset=preview, to_attr="preview_items"))
    )


def collection_position_case(numbered_items):
    """One CASE expression mapping each item primary key to its new position."""
    return Case(
        *[When(pk=item.pk, then=Value(position)) for position, item in numbered_items],
        output_field=IntegerField(),
    )


def reindex_collection_items(collection, ordered_items):
    """Rewrite positions to 0..n-1 in two statements.

    ``unique_collection_position`` forbids two rows sharing a position, so the
    rewrite first parks every row above the 200-item ceiling and then assigns the
    final positions in a single ``CASE`` update. The previous implementation
    saved each row individually, which cost one query per item — around 405
    queries to add a single title to a full collection, all under row locks.

    ``ordered_items`` may contain one unsaved row (an insert): positions are
    taken from its index in the desired order, so the caller can save that row
    afterwards at the slot reserved for it.
    """
    numbered = [(position, item) for position, item in enumerate(ordered_items) if item.pk is not None]
    TitleCollectionItem.objects.filter(collection=collection).update(position=F("position") + 201)
    if numbered:
        TitleCollectionItem.objects.filter(pk__in=[item.pk for _, item in numbered]).update(
            position=collection_position_case(numbered)
        )
    for position, item in numbered:
        item.position = position


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
        ).prefetch_related(*title_payload_prefetch("title"))
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
            LibraryEntry.objects.select_related("title", "title__franchise").prefetch_related(
                *title_payload_prefetch("title")
            ),
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
            *title_payload_prefetch("title")
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
            *episode_payload_prefetch("episode"),
            *title_payload_prefetch("episode__title"),
        )


class HistoryEntryView(APIView):
    """Per-title history resource of the signed-in viewer.

    DELETE removes every history mark of one title: the home resume shelf and
    the history page offer "remove from history" per title, not per episode,
    because partial deletion would immediately re-derive the shelf from the
    remaining rows and look like a no-op.

    GET returns the compact per-episode marks the player episode rail needs:
    which episode numbers the viewer has already watched. The response stays
    small (a list of integers) even for a thousand-episode series, unlike the
    paginated history list whose rows carry full title payloads.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        get_object_or_404(Title, slug=slug)
        watched_numbers = list(
            EpisodeProgress.objects.filter(
                user=request.user,
                episode__title__slug=slug,
                episode__season_number=1,
                is_watched=True,
            )
            .order_by("episode__number")
            .values_list("episode__number", flat=True)
        )
        return Response({"watched_episode_numbers": watched_numbers})

    def delete(self, request, slug):
        deleted, _ = EpisodeProgress.objects.filter(
            user=request.user, episode__title__slug=slug
        ).delete()
        if not deleted:
            raise Http404
        return Response(status=status.HTTP_204_NO_CONTENT)


class EpisodeProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get_episode(self, slug, number):
        return get_object_or_404(
            Episode.objects.select_related("title").prefetch_related(playback_sources_prefetch()),
            title__slug=slug,
            number=number,
            # A special can share the number, and this endpoint is the
            # work's own run.
            season_number=1,
        )

    def get_progress(self, request, slug, number):
        return get_object_or_404(
            EpisodeProgress.objects.select_related(
                "episode", "episode__title", "episode__title__franchise"
            ).prefetch_related(
                playback_sources_prefetch("episode__sources"),
                *episode_payload_prefetch("episode"),
                *title_payload_prefetch("episode__title"),
            ),
            user=request.user,
            episode__title__slug=slug,
            episode__number=number,
            episode__season_number=1,
        )

    def get(self, request, slug, number):
        return Response(EpisodeProgressSerializer(self.get_progress(request, slug, number)).data)

    def post(self, request, slug, number):
        episode = self.get_episode(slug, number)
        # The player reports which voice-over variant it is about to play so
        # the resume shelf can restore the same version later.
        selection = EpisodeSourceSelectionSerializer(data=request.data)
        selection.is_valid(raise_exception=True)
        source_fields = {
            key: value
            for key, value in selection.validated_data.items()
            if key.startswith("source_")
        }
        progress, created = EpisodeProgress.objects.update_or_create(
            user=request.user,
            episode=episode,
            defaults={"last_opened_at": timezone.now(), **source_fields},
        )
        # Optional convenience: the first playback can file the title under
        # "watching" automatically, keeping the library counters honest about
        # what the viewer actually started.
        if request.user.auto_add_to_watching and not LibraryEntry.objects.filter(
            user=request.user, title_id=episode.title_id
        ).exists():
            LibraryEntry.objects.create(
                user=request.user,
                title_id=episode.title_id,
                status=LibraryEntry.Status.WATCHING,
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

    def patch(self, request, slug, number):
        serializer = EpisodePlaybackProgressWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        episode = self.get_episode(slug, number)
        incoming = serializer.validated_data
        now = timezone.now()

        # The row lock and monotonic maxima make delayed or repeated player
        # messages idempotent while preventing concurrent heartbeats from
        # moving a user's progress backwards.
        with transaction.atomic():
            progress, created = EpisodeProgress.objects.select_for_update().get_or_create(
                user=request.user,
                episode=episode,
                defaults={"last_opened_at": now},
            )
            progress.last_opened_at = max(progress.last_opened_at, now)
            progress.duration_seconds = max(
                progress.duration_seconds or 0,
                incoming["duration_seconds"],
            )
            progress.watched_seconds = max(
                progress.watched_seconds,
                incoming["watched_seconds"],
            )

            if incoming["event"] == "ended":
                progress.watched_seconds = progress.duration_seconds
            completed = (
                incoming["event"] == "ended"
                or progress.watched_seconds * 100 >= progress.duration_seconds * 90
            )
            if completed and not progress.is_watched:
                progress.is_watched = True
                progress.watched_at = now
            # A voice switch mid-episode updates the snapshot too, so resume
            # restores what the viewer played last, not the first variant.
            for field in ("source_selection_key", "source_name", "source_kind"):
                if incoming.get(field):
                    setattr(progress, field, incoming[field])

            progress.save(
                update_fields=[
                    "last_opened_at",
                    "duration_seconds",
                    "watched_seconds",
                    "is_watched",
                    "watched_at",
                    "source_selection_key",
                    "source_name",
                    "source_kind",
                    "updated_at",
                ]
            )

        return Response(
            EpisodePlaybackProgressSerializer(progress).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ContinueWatchingView(APIView):
    """Resume shelf for the home page.

    Built only from recorded playback starts. Resume targets are guaranteed to
    have an authorized source; completed and currently unplayable titles do not
    become dead cards on the home page. Titles hidden through the shelf menu
    stay out until explicitly restored; hiding never removes history.

    The shelf is uncapped on purpose: every title the viewer started and has not
    finished belongs here. The resume target is resolved for the whole shelf in
    a single query, so removing the cap does not turn the page into one lookup
    per title.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        hidden_ids = set(
            ContinueWatchingHidden.objects.filter(user=request.user).values_list("title_id", flat=True)
        )
        # A title marked watched by hand leaves the shelf even while playback
        # rows still exist: the explicit library status is the stronger signal,
        # and a "Просмотрено" card inside "Продолжить просмотр" contradicts
        # itself. Hiding stays separate — it never touched the library entry.
        completed_ids = set(
            LibraryEntry.objects.filter(
                user=request.user, status=LibraryEntry.Status.COMPLETED
            ).values_list("title_id", flat=True)
        )
        excluded_ids = hidden_ids | completed_ids
        progress_entries = list(
            EpisodeProgress.objects.filter(user=request.user)
            .exclude(episode__title_id__in=excluded_ids)
            .select_related("episode", "episode__title", "episode__title__franchise")
            .prefetch_related(
                *episode_payload_prefetch("episode"),
                *title_payload_prefetch("episode__title"),
            )
            .order_by("-last_opened_at", "-id")
        )
        latest_by_title: dict[int, EpisodeProgress] = {}
        highest_watched: dict[int, int] = {}
        for entry in progress_entries:
            title_id = entry.episode.title_id
            if title_id not in latest_by_title:
                latest_by_title[title_id] = entry
            if entry.is_watched:
                highest_watched[title_id] = max(highest_watched.get(title_id, 0), entry.episode.number)
        if not latest_by_title:
            return Response([])
        title_ids = list(latest_by_title)
        watched_counts = {
            row["episode__title_id"]: row["count"]
            for row in EpisodeProgress.objects.filter(
                user=request.user,
                is_watched=True,
                episode__title_id__in=title_ids,
            ).values("episode__title_id").annotate(count=Count("id"))
        }
        # An opened-but-unwatched episode resumes on itself; a watched one starts
        # after the highest watched number. One OR of per-title thresholds
        # resolves the whole shelf, ordered so the first authorized source per
        # title wins; the per-title loop this replaces was bounded by the shelf
        # cap, which no longer exists.
        resume_after = {
            title_id: (
                highest_watched.get(title_id, entry.episode.number)
                if entry.is_watched
                else entry.episode.number - 1
            )
            for title_id, entry in latest_by_title.items()
        }
        resume_by_title: dict[int, Episode] = {}
        resume_after_filter = Q()
        for title_id, threshold in resume_after.items():
            resume_after_filter |= Q(
                episode__title_id=title_id,
                episode__number__gt=threshold,
                episode__season_number=1,
            )
        if resume_after_filter:
            candidates = (
                playback_source_queryset()
                .filter(resume_after_filter)
                .order_by("episode__title_id", "episode__number", "id")
            )
            for source in candidates.iterator(chunk_size=500):
                title_id = source.episode.title_id
                if title_id in resume_by_title:
                    continue
                if playback_available(source):
                    resume_by_title[title_id] = source.episode
        # The source queryset joins the episode but not its translations, and
        # every resume episode is serialized twice below. Re-hydrating them in
        # one query keeps the localized name out of the per-row path.
        if resume_by_title:
            localized_episodes = {
                episode.pk: episode
                for episode in Episode.objects.filter(
                    pk__in=[episode.pk for episode in resume_by_title.values()]
                ).prefetch_related(*episode_payload_prefetch())
            }
            resume_by_title = {
                title_id: localized_episodes.get(episode.pk, episode)
                for title_id, episode in resume_by_title.items()
            }
        context = {"request": request}
        ordered = sorted(latest_by_title.values(), key=lambda entry: entry.last_opened_at, reverse=True)
        # The resume shelf renders "episode N of M", so the titles need the same
        # episodes_count aggregate the catalog list already annotates — one
        # extra COUNT over at most title_limit titles, not one per row.
        episodes_total = dict(
            Episode.objects.filter(title_id__in=title_ids)
            .values_list("title_id")
            .annotate(total=Count("id"))
        ) if title_ids else {}
        for entry in ordered:
            setattr(entry.episode.title, "episodes_count", episodes_total.get(entry.episode.title_id, 0))

        # "Next part of your story": for every started franchise title, the
        # franchise sibling that follows it in watch order. This is separate
        # from recommendations — it is the viewer's own unfinished story.
        franchise_ids = {
            entry.episode.title.franchise_id
            for entry in ordered
            if entry.episode.title.franchise_id is not None
        }
        franchise_siblings: dict[int, list[Title]] = {}
        if franchise_ids:
            sibling_rows = (
                Title.objects.filter(franchise_id__in=franchise_ids)
                .only("id", "franchise_id", "name", "slug", "poster_url", "year")
                .prefetch_related("translations")
            )
            for sibling in sibling_rows:
                franchise_siblings.setdefault(sibling.franchise_id, []).append(sibling)
            for siblings in franchise_siblings.values():
                siblings.sort(key=lambda title: (title.year is None, title.year or 0, title.name, title.id))

        def franchise_next_payload(entry: EpisodeProgress):
            title = entry.episode.title
            if title.franchise_id is None:
                return None
            siblings = franchise_siblings.get(title.franchise_id, [])
            following = [sibling for sibling in siblings if sibling.pk != title.pk]
            if not following:
                return None
            # The sibling list is sorted in watch order; the part after the
            # current one is the first sibling positioned after this title.
            position = next(
                (index for index, sibling in enumerate(siblings) if sibling.pk == title.pk),
                len(siblings),
            )
            after = siblings[position + 1] if position + 1 < len(siblings) else following[0]
            return {
                "name": translated_value(after, "name", {"request": request}),
                "slug": after.slug,
                "poster_url": posters.public_poster_reference(after.poster_url),
                "year": after.year,
            }

        response_rows = []
        for entry in ordered:
            title_id = entry.episode.title_id
            if title_id not in resume_by_title:
                continue
            resume_episode = resume_by_title[title_id]
            same_episode = resume_episode.pk == entry.episode_id
            response_rows.append({
                "title": TitleSerializer(entry.episode.title, context=context).data,
                "last_episode": ShelfEpisodeSerializer(entry.episode, context=context).data,
                "resume_episode": ShelfEpisodeSerializer(resume_episode, context=context).data,
                # Temporary compatibility for the previous frontend release.
                "next_episode": ShelfEpisodeSerializer(resume_episode, context=context).data,
                "is_watched": entry.is_watched,
                "watched_count": watched_counts.get(title_id, 0),
                "resume_at_seconds": entry.watched_seconds if same_episode else 0,
                "duration_seconds": entry.duration_seconds if same_episode else None,
                "progress_percent": entry.progress_percent if same_episode else 0,
                # Voice-over snapshot of what the viewer actually played, so
                # "continue" restores the same variant instead of the default.
                "source_selection_key": entry.source_selection_key,
                "source_name": entry.source_name,
                "source_kind": entry.source_kind,
                "franchise_next": franchise_next_payload(entry),
                "last_opened_at": entry.last_opened_at,
            })
        return Response(response_rows)


class ContinueWatchingHideView(APIView):
    """Shelf-level removal of one title from the resume list.

    POST hides the card, DELETE restores it. History rows and the library
    entry are never touched: an accidental playback can be swept off the shelf
    without losing real progress.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        title = get_object_or_404(Title, slug=slug)
        _, created = ContinueWatchingHidden.objects.get_or_create(user=request.user, title=title)
        return Response(status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, slug):
        deleted, _ = ContinueWatchingHidden.objects.filter(
            user=request.user, title__slug=slug
        ).delete()
        if not deleted:
            raise Http404
        return Response(status=status.HTTP_204_NO_CONTENT)


class LibraryStatusesView(APIView):
    """Compact status map of the viewer's whole library.

    Catalog and recommendation cards need to show "Смотрю"/"В планах" chips
    and a quick "+ В планы" action without one request per card. One response
    covers every entry; the payload is a slug-keyed list, not nested titles.
    Bounded at 2000 entries with an explicit truncated flag: larger libraries
    page through LibraryEntryView instead of growing this response without bound.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        entries = list(LibraryEntry.objects.filter(user=request.user).select_related("title").only(
            "status", "is_favorite", "title__slug"
        )[:2001])
        truncated = len(entries) > 2000
        return Response({
            "entries": [
                {"slug": entry.title.slug, "status": entry.status, "is_favorite": entry.is_favorite}
                for entry in entries[:2000]
            ],
            "truncated": truncated,
        })


class TitleNoteListView(ListAPIView):
    serializer_class = TitleNoteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LibraryPagination

    def get_queryset(self):
        return TitleNote.objects.filter(user=self.request.user).select_related(
            "title", "title__franchise"
        ).prefetch_related(*title_payload_prefetch("title"))


class TitleNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get_note(self, request, slug):
        return get_object_or_404(
            TitleNote.objects.select_related("title", "title__franchise").prefetch_related(
                *title_payload_prefetch("title")
            ),
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
        note = TitleNote.objects.select_related("title", "title__franchise").prefetch_related(
            *title_payload_prefetch("title")
        ).get(pk=note.pk)
        return Response(TitleNoteSerializer(note).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, slug):
        self.get_note(request, slug).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def rating_subquery_annotations() -> dict[str, Subquery]:
    """Community rating aggregates as correlated subqueries.

    The recommendation queryset joins genres for scoring, so join-based
    aggregates (catalog's annotate_rating_aggregates) would multiply the
    score sum by the rating count; subqueries keep both independent.
    Deactivated accounts are excluded, matching the review takedown.
    """

    stats = TitleRating.objects.filter(title=OuterRef("pk"), user__is_active=True).values("title")
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
    # Recommendations must widen the choice, not replay one franchise: only
    # this many titles per franchise survive, regardless of score. One
    # representative is enough — the franchise page and the title's own watch
    # order already answer "what else is in this story". Franchises the viewer
    # already engaged with are excluded entirely; their continuations live in
    # the "next part of your story" shelf instead.
    per_franchise_cap = 1
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

    def _apply_franchise_cap(self, queryset):
        """Keep at most `per_franchise_cap` titles of any one franchise.

        The boost makes engaged franchises dominate the top of the list; a
        viewer who just watched one part does not need a row of its sequels,
        so a franchise gets a single representative in the recommendations.
        Titles without a franchise pass through untouched. The id list is
        evaluated once in score order; the catalog is small, so this stays
        cheaper than a window-function reimplementation of the same cap.
        """
        rows = list(queryset.values_list("id", "franchise_id"))
        seen: dict[int, int] = {}
        kept: list[int] = []
        for title_id, franchise_id in rows:
            if franchise_id is None:
                kept.append(title_id)
                continue
            count = seen.get(franchise_id, 0)
            if count >= self.per_franchise_cap:
                continue
            seen[franchise_id] = count + 1
            kept.append(title_id)
        if len(kept) == len(rows):
            return queryset
        return queryset.filter(id__in=kept)

    def get_queryset(self):
        user = self.request.user
        # Franchises the viewer already touched (any library entry or any
        # playback) are their own story, not a "recommendation". Their next
        # parts belong to the dedicated "next part of your story" shelf, so
        # recommendations stay about new stories.
        engaged_franchise_ids = (
            set(
                LibraryEntry.objects.filter(user=user, title__franchise_id__isnull=False)
                .values_list("title__franchise_id", flat=True)
            )
            | set(
                EpisodeProgress.objects.filter(user=user, episode__title__franchise_id__isnull=False)
                .values_list("episode__title__franchise_id", flat=True)
            )
        )
        excluded_ids = (
            set(LibraryEntry.objects.filter(user=user).values_list("title_id", flat=True))
            | self._fully_watched_title_ids()
            # Any watch progress at all means the viewer already found the
            # title; a partially watched series must not reappear as a
            # "recommendation" next to its own Continue Watching row.
            | set(
                EpisodeProgress.objects.filter(user=user).values_list("episode__title_id", flat=True)
            )
            | set(RecommendationDismissal.objects.filter(user=user).values_list("title_id", flat=True))
        )
        queryset = (
            Title.objects.exclude(id__in=excluded_ids)
            .exclude(franchise_id__in=engaged_franchise_ids)
            .select_related("franchise")
            .prefetch_related("translations", "franchise__translations", "genres", "genres__translations")
        )
        # Within a franchise the entry point (earliest part) is the useful
        # recommendation; a random later season assumes context the viewer
        # does not have. Unfranchised titles are entry points by definition.
        franchise_entry = (
            Title.objects.filter(franchise=OuterRef("franchise"))
            .order_by(F("year").asc(nulls_last=True), "name", "id")
            .values("pk")[:1]
        )
        queryset = queryset.annotate(
            is_franchise_entry=Case(
                When(franchise__isnull=True, then=Value(1)),
                When(pk=Subquery(franchise_entry), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        weights, engagement = self._signals()
        positive_genres = [genre_id for genre_id, weight in sorted(weights.items()) if weight > 0]
        if not positive_genres:
            # Cold start or only negative signals: an honest recency fallback.
            return self._apply_franchise_cap(queryset.annotate(score=Value(0.0, output_field=FloatField())).order_by(
                "-is_franchise_entry",
                F("year").desc(nulls_last=True),
                "name",
                "slug",
            ))
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
        return self._apply_franchise_cap(
            queryset.filter(id__in=Subquery(candidates))
            .annotate(**rating_subquery_annotations(), score=score)
            .order_by(
                "-score",
                "-is_franchise_entry",
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
        collections = collection_summary_queryset().filter(owner=request.user)
        context = {"request": request}
        # The title page asks one question of this endpoint: which collections
        # already contain the title being viewed. Answering it here keeps the
        # client from needing the full nested item list of every collection.
        title_slug = request.query_params.get("title", "").strip()[:260]
        if title_slug:
            context["membership_title_slug"] = title_slug
            context["membership_collection_ids"] = set(
                TitleCollectionItem.objects.filter(
                    collection__owner=request.user, title__slug=title_slug
                ).values_list("collection_id", flat=True)
            )
        return Response(CollectionSummarySerializer(collections, many=True, context=context).data)

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
            # Insert by rewriting the whole order once: the new row takes its
            # slot in the list and reindex assigns every final position in a
            # single statement, instead of shifting rows one save at a time.
            item = TitleCollectionItem(collection=collection, title=title, position=position)
            ordered = items[:position] + [item] + items[position:]
            reindex_collection_items(collection, ordered)
            item.position = position
            item.save()
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
        # `owner__is_active` matters here: deactivating an account is the takedown
        # mechanism, and it already hides the profile, so leaving public
        # collections readable would make that takedown partial.
        collection = get_object_or_404(
            collection_queryset(),
            owner__public_id=public_id,
            owner__is_active=True,
            slug=slug,
            is_public=True,
        )
        return Response(PublicCollectionSerializer(collection, context={"request": request}).data)
