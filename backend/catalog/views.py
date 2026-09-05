from datetime import timedelta

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.http import FileResponse, HttpResponseBase, HttpResponseNotFound, HttpRequest, HttpResponseRedirect
from django.db.models import Avg, Case, Count, F, FloatField, Prefetch, Q, Value, When
from django.db.models.functions import Cast
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_safe
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle

from . import posters
from .models import (
    Character,
    Creator,
    Episode,
    Franchise,
    Genre,
    MediaAsset,
    Provider,
    RightsGrant,
    Source,
    SourceReport,
    Title,
    TitleCredit,
)
from .playback import (
    issue_playback,
    legacy_source_selection_key_parts,
    playback_sources_prefetch,
    playback_url_allowed,
    resolve_playback,
    source_provider_variant_id_parts,
    source_selection_key_parts,
    validate_provider_configuration,
)
from .search import search_characters, search_franchises, search_titles
from .serializers import (
    EpisodeDetailSerializer,
    FranchiseDetailSerializer,
    FranchiseSummarySerializer,
    CharacterDetailSerializer,
    CharacterSummarySerializer,
    CreatorDetailSerializer,
    GenreOptionSerializer,
    MediaAssetSerializer,
    ScheduleEpisodeSerializer,
    SourceReportSerializer,
    TitleDetailSerializer,
    TitleSerializer,
)


class CatalogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


# Public catalog data changes on the sync cadence (Kodik hourly, Jikan every 15
# minutes), not per request, so a short shared window is honest. `Vary` is the
# load-bearing part: the payload is localized from ?lang=, the anicast_lang
# cookie and Accept-Language, and DRF already varies on Accept for content
# negotiation. Getting that wrong would serve one visitor's language to another.
PUBLIC_CACHE_SECONDS = 60
PUBLIC_STALE_WHILE_REVALIDATE_SECONDS = 300


class PublicCacheMixin:
    """Attach shared-cache headers to safe, anonymous catalog responses.

    Authenticated responses are excluded: DRF varies on Cookie, but a shared
    cache that ignores it would leak one session's payload to another, and no
    catalog endpoint returns anything personal that is worth that risk.
    """

    cache_seconds = PUBLIC_CACHE_SECONDS

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        cacheable = (
            request.method in ("GET", "HEAD")
            and response.status_code == 200
            and not request.user.is_authenticated
            and not response.has_header("Cache-Control")
        )
        if cacheable:
            response["Cache-Control"] = (
                f"public, max-age=0, s-maxage={self.cache_seconds}, "
                f"stale-while-revalidate={PUBLIC_STALE_WHILE_REVALIDATE_SECONDS}"
            )
            patch_vary_headers(response, ("Accept-Language", "Cookie"))
        return response


def annotate_rating_aggregates(queryset):
    """Attach community rating aggregates and the episode count for
    TitleSerializer. The annotations are part of the list SELECT, so serialized
    cards never query ratings or episodes per row; unannotated querysets simply
    serialize nulls."""
    return queryset.annotate(
        rating_count=Count("ratings", distinct=True),
        rating_avg=Avg("ratings__value"),
        episodes_count=Count("episodes", distinct=True),
    )


class TitleListView(PublicCacheMixin, ListAPIView):
    serializer_class = TitleSerializer
    pagination_class = CatalogPagination
    # Ordering stays opt-in: without the parameter the queryset keeps the
    # model default (name), so existing catalog URLs are unaffected.
    ordering_options = frozenset({"popular", "recent", "name"})

    def get_queryset(self):
        queryset = Title.objects.select_related("franchise").prefetch_related(
            "translations", "franchise__translations", "genres", "genres__translations"
        )
        params = self.request.query_params
        query = params.get("q", "").strip()[:120]
        if query:
            queryset = search_titles(queryset, query)
        if genre := params.get("genre", "").strip():
            queryset = queryset.filter(genres__slug=genre)
        if status := params.get("status", "").strip():
            queryset = queryset.filter(status=status)
        if title_type := params.get("type", "").strip():
            queryset = queryset.filter(title_type=title_type)
        queryset = queryset.distinct()
        ordering = params.get("ordering", "").strip()
        if ordering and ordering not in self.ordering_options:
            raise ValidationError({"ordering": "Неизвестный порядок сортировки."})
        if ordering == "popular":
            # Popularity is derived from real engagement only: library adds and
            # submitted ratings. Without engagement the fallback stays factual.
            queryset = queryset.annotate(
                popularity=Count("library_entries", distinct=True) + Count("ratings", distinct=True)
            ).order_by("-popularity", F("year").desc(nulls_last=True), "name", "slug")
            return annotate_rating_aggregates(queryset)
        if ordering == "recent":
            return annotate_rating_aggregates(queryset).order_by(
                F("year").desc(nulls_last=True), "name", "slug"
            )
        # Unique tiebreaker keeps LIMIT/OFFSET pagination deterministic on
        # Postgres when several titles share a name.
        return annotate_rating_aggregates(queryset).order_by("name", "slug")


class EpisodePagination(PageNumberPagination):
    page_size = 20
    page_query_param = "episodes_page"
    page_size_query_param = "episodes_page_size"
    max_page_size = 50


class CharacterPagination(PageNumberPagination):
    page_size = 60
    page_query_param = "characters_page"
    page_size_query_param = "characters_page_size"
    max_page_size = 100


class TitleDetailView(PublicCacheMixin, RetrieveAPIView):
    # Episodes are fetched by the serializer as a paginated queryset, so the
    # detail view never loads the full episode list of a long-running series.
    queryset = annotate_rating_aggregates(
        Title.objects.annotate(episodes_count=Count("episodes", distinct=True)).select_related(
            "franchise"
        ).prefetch_related(
            "translations", "franchise__translations", "genres", "genres__translations",
            Prefetch("credits", queryset=TitleCredit.objects.select_related("creator")),
            Prefetch(
                "franchise__titles",
                queryset=Title.objects.prefetch_related("translations"),
                to_attr="related_titles_prefetched",
            ),
        )
    )
    serializer_class = TitleDetailSerializer
    lookup_field = "slug"
    # Hard ceiling for the `episodes_from`/`episodes_to` window: one screen of
    # the player episode rail never needs more, and a shared-cache edge must
    # not store arbitrary full-series slices under unique query keys.
    EPISODE_RANGE_WINDOW_LIMIT = 500

    def parse_episode_number_range(self, request):
        """Optional inclusive episode-number window for the episodes list.

        Returns None when neither parameter is supplied. Explicitly wrong
        input (non-integer, reversed, non-positive, oversized window) raises
        ValidationError instead of being silently ignored: a caller slicing by
        number must learn its request is malformed, not receive page one.
        """
        raw_from = request.query_params.get("episodes_from")
        raw_to = request.query_params.get("episodes_to")
        if raw_from is None and raw_to is None:
            return None
        try:
            number_from = int(raw_from) if raw_from is not None else 1
            # An omitted upper bound still cannot widen the window beyond the
            # ceiling, otherwise "episodes_from=1" alone would request the
            # whole series.
            number_to = int(raw_to) if raw_to is not None else number_from + self.EPISODE_RANGE_WINDOW_LIMIT - 1
        except (TypeError, ValueError):
            raise ValidationError("episodes_from/episodes_to must be integers.")
        if number_from < 1 or number_to < number_from:
            raise ValidationError("episodes_from/episodes_to must satisfy 1 <= from <= to.")
        if number_to - number_from + 1 > self.EPISODE_RANGE_WINDOW_LIMIT:
            raise ValidationError(
                f"The episode number window may span at most {self.EPISODE_RANGE_WINDOW_LIMIT} episodes."
            )
        return number_from, number_to

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Episode and cast lists are always bounded. One Piece alone has 1180
        # episodes and 4200+ sources, so an unpaginated detail response was a
        # single request that could serialize the whole series; clients read
        # episodes_count / characters_count and page explicitly. The paginator
        # keeps honoring episodes_page / episodes_page_size when supplied.
        context["episodes_paginator"] = EpisodePagination()
        context["characters_paginator"] = CharacterPagination()
        context["include_episode_sources"] = self.request.query_params.get("episode_sources") != "0"
        context["episode_number_range"] = self.parse_episode_number_range(self.request)
        return context


class CreatorDetailView(PublicCacheMixin, RetrieveAPIView):
    queryset = Creator.objects.prefetch_related(
        Prefetch(
            "title_credits",
            queryset=TitleCredit.objects.select_related("title", "title__franchise").prefetch_related(
                "title__translations", "title__genres", "title__genres__translations",
                "title__franchise__translations",
            ),
        )
    )
    serializer_class = CreatorDetailSerializer
    lookup_field = "slug"


class EpisodeDetailView(PublicCacheMixin, APIView):
    def get(self, request, slug, number):
        episode = get_object_or_404(
            Episode.objects.select_related("title").prefetch_related(
                "translations", playback_sources_prefetch()
            ),
            title__slug=slug,
            number=number,
        )
        return Response(EpisodeDetailSerializer(episode, context={"request": request}).data)


class WatchNavigationView(PublicCacheMixin, APIView):
    """Compact episode/voice-over matrix for the unified watch screen.

    The response contains no provider URL. Playback remains available only via
    the short-lived signed resolver used by the episode detail endpoint.
    """

    permission_classes = [AllowAny]

    def get(self, request, slug):
        title = get_object_or_404(Title, slug=slug)
        catalog_episode_numbers = list(
            Episode.objects.filter(title=title).order_by("number").values_list("number", flat=True)
        )
        now = timezone.now()
        provider_context = {}
        entitled_provider_ids = []
        providers = Provider.objects.filter(
            sources__episode__title=title,
            is_enabled=True,
        ).distinct()
        for provider in providers:
            try:
                _, _, allowed_hosts = validate_provider_configuration(
                    provider.playback_adapter,
                    provider.playback_config,
                    provider.allowed_hosts,
                )
            except (TypeError, ValueError):
                continue
            provider_context[provider.id] = (provider.slug, provider.name, allowed_hosts)
            if (
                provider.rights_reference
                and provider.rights_verified_at
                and (provider.rights_valid_until is None or provider.rights_valid_until > now)
            ):
                entitled_provider_ids.append(provider.id)

        rights_filter = Q(provider_id__in=entitled_provider_ids) | Q(
            rights_grants__status=RightsGrant.Status.ACTIVE,
            rights_grants__valid_from__lte=now,
            rights_grants__valid_until__gt=now,
            rights_grants__approved_by__isnull=False,
            rights_grants__approved_at__isnull=False,
        )
        rows = (
            Source.objects.filter(
                episode__title=title,
                availability="available",
                provider_id__in=provider_context,
            )
            .filter(rights_filter)
            .values_list(
                "provider_id", "episode__number", "name", "kind", "external_id", "url", "playback_count"
            )
            .distinct()
            .order_by("kind", "name", "provider_id", "episode__number")
        )
        groups = {}
        for provider_id, episode_number, name, kind, external_id, url, playback_count in rows:
            provider_slug, provider_name, allowed_hosts = provider_context[provider_id]
            if not playback_url_allowed(url, allowed_hosts):
                continue
            provider_variant_id = source_provider_variant_id_parts(provider_slug, external_id)
            key = source_selection_key_parts(provider_slug, kind, name, external_id)
            group = groups.setdefault(
                key,
                {
                    "key": key,
                    "legacy_key": legacy_source_selection_key_parts(provider_slug, kind, name),
                    "name": name,
                    "kind": kind,
                    "provider_name": provider_name,
                    "provider_variant_id": provider_variant_id,
                    "episode_numbers": set(),
                    "playback_count": 0,
                },
            )
            group["episode_numbers"].add(episode_number)
            group["playback_count"] += playback_count

        kind_order = {"dub": 0, "sub": 1, "raw": 2}
        source_groups = []
        total_playbacks = sum(group["playback_count"] for group in groups.values())
        for group in groups.values():
            numbers = sorted(group["episode_numbers"])
            source_groups.append({
                "key": group["key"],
                "legacy_key": group["legacy_key"],
                "name": group["name"],
                "kind": group["kind"],
                "provider_name": group["provider_name"],
                "provider_variant_id": group["provider_variant_id"],
                "episode_numbers": numbers,
                "episodes_count": len(numbers),
                "popularity_percent": round(group["playback_count"] * 100 / total_playbacks) if total_playbacks else 0,
                "_playback_count": group["playback_count"],
            })
        source_groups.sort(
            key=lambda group: (
                -group["_playback_count"],
                -group["episodes_count"],
                kind_order.get(group["kind"], 9),
                group["name"].casefold(),
                group["key"],
            )
        )
        for group in source_groups:
            group.pop("_playback_count")
        playable_episode_numbers = sorted(
            {number for group in source_groups for number in group["episode_numbers"]}
        )
        return Response({
            "catalog_episode_numbers": catalog_episode_numbers,
            "playable_episode_numbers": playable_episode_numbers,
            # Expand-only compatibility alias for clients released before the
            # catalog/playable distinction was exposed explicitly.
            "episode_numbers": playable_episode_numbers,
            "source_groups": source_groups,
        })


class SimilarTitleListView(PublicCacheMixin, ListAPIView):
    serializer_class = TitleSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    similar_limit = 12
    franchise_bonus = 2.0

    def get_queryset(self):
        title = get_object_or_404(Title, slug=self.kwargs["slug"])
        genre_ids = list(title.genres.values_list("id", flat=True))
        queryset = (
            Title.objects.exclude(pk=title.pk)
            .select_related("franchise")
            .prefetch_related("translations", "franchise__translations", "genres", "genres__translations")
        )
        if not genre_ids:
            if title.franchise_id:
                scored = queryset.filter(franchise_id=title.franchise_id).order_by("name", "slug")
                return annotate_rating_aggregates(scored)[: self.similar_limit]
            return queryset.none()
        score: object = Count("genres", filter=Q(genres__id__in=genre_ids), distinct=True)
        if title.franchise_id:
            score = Cast(score, FloatField()) + Case(
                When(franchise_id=title.franchise_id, then=Value(self.franchise_bonus)),
                default=Value(0.0),
                output_field=FloatField(),
            )
        scored = (
            queryset.filter(genres__id__in=genre_ids)
            .annotate(similarity=score)
            .distinct()
            .order_by("-similarity", "name", "slug")
        )
        return annotate_rating_aggregates(scored)[: self.similar_limit]


class SchedulePagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 200


class ScheduleView(PublicCacheMixin, ListAPIView):
    serializer_class = ScheduleEpisodeSerializer
    pagination_class = SchedulePagination

    def get_queryset(self):
        today = timezone.localdate()
        raw_start = self.request.query_params.get("from")
        raw_end = self.request.query_params.get("to")
        start = parse_date(raw_start) if raw_start else today
        if start is None:
            raise ValidationError({"date": "Используйте формат даты YYYY-MM-DD."})
        end = parse_date(raw_end) if raw_end else start + timedelta(days=6)
        if end is None:
            raise ValidationError({"date": "Используйте формат даты YYYY-MM-DD."})
        if end < start:
            raise ValidationError({"date": "Конечная дата не может быть раньше начальной."})
        if (end - start).days > 30:
            raise ValidationError({"date": "Диапазон расписания не может превышать 31 день."})
        # `air_at` sorts first when it is known so a day keeps its real broadcast
        # order; episodes with only a confirmed date fall back to title/number.
        return Episode.objects.filter(air_date__range=(start, end)).select_related("title").prefetch_related(
            "translations", "title__translations"
        ).order_by(
            "air_date", F("air_at").asc(nulls_last=True), "title__name", "number"
        )


class SourceReportThrottle(UserRateThrottle):
    rate = "10/hour"


class SourceReportView(ListAPIView):
    serializer_class = SourceReportSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [SourceReportThrottle]
    pagination_class = CatalogPagination

    def get_throttles(self):
        return [] if self.request.method == "GET" else super().get_throttles()

    def get_queryset(self):
        return SourceReport.objects.filter(reporter=self.request.user).select_related(
            "source", "source__episode", "source__episode__title"
        )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report = serializer.save(reporter=request.user)
        except IntegrityError:
            raise ValidationError({"reason": "Такая жалоба уже находится на рассмотрении."}) from None
        return Response(self.get_serializer(report).data, status=201)


class PlaybackView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "playback"

    def get(self, request, source_id):
        playback = issue_playback(source_id)
        if playback is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("Источник недоступен для просмотра.")
        response = Response({"mode": playback.mode, "url": playback.url, "expires_at": playback.expires_at})
        response["Cache-Control"] = "no-store, private"
        return response


class PlaybackResolveView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "playback"

    def get(self, request, token):
        resolved = resolve_playback(token)
        if resolved is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("Ссылка просмотра недействительна или истекла.")
        source_id, target = resolved
        Source.objects.filter(pk=source_id).update(playback_count=F("playback_count") + 1)
        response = HttpResponseRedirect(target)
        response["Cache-Control"] = "no-store, private"
        response["Referrer-Policy"] = "no-referrer"
        return response


class FranchiseListView(PublicCacheMixin, ListAPIView):
    serializer_class = FranchiseSummarySerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = Franchise.objects.annotate(title_count=Count("titles")).filter(title_count__gt=1).prefetch_related(
            "translations", Prefetch("titles", queryset=Title.objects.only("franchise_id", "poster_url", "year"))
        ).order_by(
            "sort_order", "name"
        )
        if query := self.request.query_params.get("q", "").strip()[:120]:
            queryset = search_franchises(queryset, query)
        return queryset


class GenreListView(PublicCacheMixin, ListAPIView):
    """Public genre list for the catalog filter bar, most used first. Genres
    without titles are useless as filters, so they are excluded."""

    serializer_class = GenreOptionSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Genre.objects.annotate(titles_count=Count("titles", distinct=True))
            .filter(titles_count__gt=0)
            .prefetch_related("translations")
            .order_by("-titles_count", "name")
        )


class GlobalSearchView(PublicCacheMixin, APIView):
    """Cross-entity search used by the header: titles, characters and franchises
    in one response so the suggestion panel needs a single request."""

    permission_classes = [AllowAny]
    # Each entity is one trigram-indexed lookup (see catalog/search.py). Repeated
    # terms are the common case for a suggestion panel, so a shared cache still
    # absorbs the duplicates that debounce alone cannot.
    cache_seconds = 300
    group_limit = 5
    min_query_length = 2
    max_query_length = 120

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < self.min_query_length:
            raise ValidationError({"q": "Запрос должен содержать не менее двух символов."})
        # Bound the term so an oversized value cannot turn into an expensive
        # multi-table scan.
        query = query[: self.max_query_length]
        context = {"request": request}
        titles = annotate_rating_aggregates(
            search_titles(Title.objects.all(), query)
        ).select_related("franchise").prefetch_related(
            "translations", "franchise__translations", "genres", "genres__translations"
        ).order_by("name", "slug")[: self.group_limit]
        characters = (
            search_characters(Character.objects.all(), query)
            .annotate(title_count=Count("titles", distinct=True))
            .prefetch_related("translations")
            .order_by("name", "slug")[: self.group_limit]
        )
        franchises = (
            search_franchises(Franchise.objects.all(), query)
            .annotate(title_count=Count("titles", distinct=True))
            .filter(title_count__gt=1)
            .prefetch_related(
                "translations", Prefetch("titles", queryset=Title.objects.only("franchise_id", "poster_url", "year"))
            )
            .order_by("sort_order", "name")[: self.group_limit]
        )
        return Response({
            "query": query,
            "titles": TitleSerializer(titles, many=True, context=context).data,
            "characters": CharacterSummarySerializer(characters, many=True, context=context).data,
            "franchises": FranchiseSummarySerializer(franchises, many=True, context=context).data,
        })


class FranchiseDetailView(PublicCacheMixin, RetrieveAPIView):
    serializer_class = FranchiseDetailSerializer
    lookup_field = "slug"
    queryset = Franchise.objects.annotate(title_count=Count("titles")).prefetch_related(
        "translations",
        Prefetch(
            "titles",
            queryset=Title.objects.prefetch_related("translations", "genres", "genres__translations").order_by(
                F("year").asc(nulls_last=True), "name", "slug"
            ),
        ),
    )


class CharacterListView(PublicCacheMixin, ListAPIView):
    serializer_class = CharacterSummarySerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = Character.objects.annotate(title_count=Count("titles", distinct=True)).prefetch_related("translations")
        query = self.request.query_params.get("q", "").strip()[:120]
        if query:
            queryset = search_characters(queryset, query)
        return queryset.order_by("name", "slug")


class CharacterDetailView(PublicCacheMixin, RetrieveAPIView):
    serializer_class = CharacterDetailSerializer
    lookup_field = "slug"
    queryset = Character.objects.annotate(title_count=Count("titles", distinct=True)).prefetch_related(
        "translations", "title_links__title__translations", "title_links__title__genres", "title_links__title__genres__translations"
    )


class MediaAssetListView(PublicCacheMixin, ListAPIView):
    serializer_class = MediaAssetSerializer
    pagination_class = SchedulePagination

    def get_queryset(self):
        queryset = MediaAsset.objects.filter(is_published=True).select_related("title", "character").prefetch_related(
            "translations", "title__translations", "character__translations"
        )
        if title_slug := self.request.query_params.get("title", "").strip():
            queryset = queryset.filter(title__slug=title_slug)
        if character_slug := self.request.query_params.get("character", "").strip():
            queryset = queryset.filter(character__slug=character_slug)
        if media_kind := self.request.query_params.get("kind", "").strip():
            valid_kinds = {choice for choice, _ in MediaAsset.KIND_CHOICES}
            if media_kind not in valid_kinds:
                raise ValidationError({"kind": "Неизвестный тип медиа."})
            queryset = queryset.filter(kind=media_kind)
        return queryset


POSTER_CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


@require_safe
def poster_media_view(request: HttpRequest, filename: str) -> HttpResponseBase:
    if not posters.POSTER_NAME_RE.match(filename):
        return HttpResponseNotFound()
    path = posters.media_path(filename)
    if not path.is_file():
        return HttpResponseNotFound()
    ext = filename.rsplit(".", 1)[-1]
    response = FileResponse(path.open("rb"), content_type=POSTER_CONTENT_TYPES.get(ext, "application/octet-stream"))
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response
