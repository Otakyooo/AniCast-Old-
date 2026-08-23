from datetime import timedelta

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.db.models import Case, Count, FloatField, Prefetch, Q, Value, When
from django.db.models.functions import Cast
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle

from .models import Character, Episode, Franchise, MediaAsset, SourceReport, Title
from .playback import issue_playback, playback_sources_prefetch, resolve_playback
from .serializers import (
    EpisodeDetailSerializer,
    FranchiseDetailSerializer,
    FranchiseSummarySerializer,
    CharacterDetailSerializer,
    CharacterSummarySerializer,
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


class TitleListView(ListAPIView):
    serializer_class = TitleSerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = Title.objects.select_related("franchise").prefetch_related(
            "translations", "franchise__translations", "genres", "genres__translations"
        )
        params = self.request.query_params
        query = params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(original_name__icontains=query) | Q(translations__name__icontains=query)
            )
        if genre := params.get("genre", "").strip():
            queryset = queryset.filter(genres__slug=genre)
        if status := params.get("status", "").strip():
            queryset = queryset.filter(status=status)
        if title_type := params.get("type", "").strip():
            queryset = queryset.filter(title_type=title_type)
        return queryset.distinct()


class EpisodePagination(PageNumberPagination):
    page_size = 20
    page_query_param = "episodes_page"
    page_size_query_param = "episodes_page_size"
    max_page_size = 50


class TitleDetailView(RetrieveAPIView):
    queryset = Title.objects.annotate(episodes_count=Count("episodes")).select_related(
        "franchise"
    ).prefetch_related(
        "translations", "franchise__translations", "genres", "genres__translations",
        "episodes__translations",
        playback_sources_prefetch("episodes__sources"),
    )
    serializer_class = TitleDetailSerializer
    lookup_field = "slug"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["episodes_paginator"] = EpisodePagination()
        return context


class EpisodeDetailView(APIView):
    def get(self, request, slug, number):
        episode = get_object_or_404(
            Episode.objects.select_related("title").prefetch_related(
                "translations", playback_sources_prefetch()
            ),
            title__slug=slug,
            number=number,
        )
        return Response(EpisodeDetailSerializer(episode, context={"request": request}).data)


class SimilarTitleListView(ListAPIView):
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
                return queryset.filter(franchise_id=title.franchise_id).order_by("name", "slug")[: self.similar_limit]
            return queryset.none()
        score: object = Count("genres", filter=Q(genres__id__in=genre_ids), distinct=True)
        if title.franchise_id:
            score = Cast(score, FloatField()) + Case(
                When(franchise_id=title.franchise_id, then=Value(self.franchise_bonus)),
                default=Value(0.0),
                output_field=FloatField(),
            )
        return (
            queryset.filter(genres__id__in=genre_ids)
            .annotate(similarity=score)
            .distinct()
            .order_by("-similarity", "name", "slug")[: self.similar_limit]
        )


class SchedulePagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 200


class ScheduleView(ListAPIView):
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
        return Episode.objects.filter(air_date__range=(start, end)).select_related("title").prefetch_related(
            "translations", "title__translations"
        ).order_by(
            "air_date", "title__name", "number"
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
    def get(self, request, source_id):
        playback = issue_playback(source_id)
        if playback is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("Источник недоступен для просмотра.")
        response = Response({"mode": playback.mode, "url": playback.url, "expires_at": playback.expires_at})
        response["Cache-Control"] = "no-store, private"
        return response


class PlaybackResolveView(APIView):
    def get(self, request, token):
        target = resolve_playback(token)
        if target is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("Ссылка просмотра недействительна или истекла.")
        response = HttpResponseRedirect(target)
        response["Cache-Control"] = "no-store, private"
        response["Referrer-Policy"] = "no-referrer"
        return response


class FranchiseListView(ListAPIView):
    serializer_class = FranchiseSummarySerializer
    pagination_class = CatalogPagination
    queryset = Franchise.objects.annotate(title_count=Count("titles")).prefetch_related("translations").order_by("sort_order", "name")


class FranchiseDetailView(RetrieveAPIView):
    serializer_class = FranchiseDetailSerializer
    lookup_field = "slug"
    queryset = Franchise.objects.annotate(title_count=Count("titles")).prefetch_related(
        "translations",
        Prefetch(
            "titles",
            queryset=Title.objects.prefetch_related("translations", "genres", "genres__translations").order_by("name", "slug"),
        ),
    )


class CharacterListView(ListAPIView):
    serializer_class = CharacterSummarySerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = Character.objects.annotate(title_count=Count("titles", distinct=True)).prefetch_related("translations")
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(original_name__icontains=query) | Q(translations__name__icontains=query)
            ).distinct()
        return queryset.order_by("name", "slug")


class CharacterDetailView(RetrieveAPIView):
    serializer_class = CharacterDetailSerializer
    lookup_field = "slug"
    queryset = Character.objects.annotate(title_count=Count("titles", distinct=True)).prefetch_related(
        "translations", "title_links__title__translations", "title_links__title__genres", "title_links__title__genres__translations"
    )


class MediaAssetListView(ListAPIView):
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
