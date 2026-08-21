from datetime import timedelta

from django.db import IntegrityError
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle

from .models import Episode, Franchise, SourceReport, Title
from .playback import authorized_playback_source
from .serializers import (
    FranchiseDetailSerializer,
    FranchiseSummarySerializer,
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


class TitleDetailView(RetrieveAPIView):
    queryset = Title.objects.select_related("franchise").prefetch_related(
        "translations", "franchise__translations", "genres", "genres__translations",
        "episodes__translations", "episodes__sources",
    )
    serializer_class = TitleDetailSerializer
    lookup_field = "slug"


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
        source = authorized_playback_source(source_id)
        if source is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("Источник недоступен для просмотра.")
        return Response({"mode": "external_link", "url": source.url})


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
