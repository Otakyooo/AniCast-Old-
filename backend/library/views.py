from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Episode, Title

from .models import EpisodeProgress, LibraryEntry
from .serializers import (
    EpisodeProgressSerializer,
    EpisodeProgressWriteSerializer,
    LibraryEntrySerializer,
    LibraryEntryWriteSerializer,
)


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
