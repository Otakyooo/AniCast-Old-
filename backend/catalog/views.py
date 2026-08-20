from django.db.models import Q
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination

from .models import Title
from .serializers import TitleDetailSerializer, TitleSerializer


class CatalogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class TitleListView(ListAPIView):
    serializer_class = TitleSerializer
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = Title.objects.select_related("franchise").prefetch_related("genres")
        params = self.request.query_params
        query = params.get("q", "").strip()
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(original_name__icontains=query))
        if genre := params.get("genre", "").strip():
            queryset = queryset.filter(genres__slug=genre)
        if status := params.get("status", "").strip():
            queryset = queryset.filter(status=status)
        if title_type := params.get("type", "").strip():
            queryset = queryset.filter(title_type=title_type)
        return queryset.distinct()


class TitleDetailView(RetrieveAPIView):
    queryset = Title.objects.select_related("franchise").prefetch_related("genres", "episodes__sources")
    serializer_class = TitleDetailSerializer
    lookup_field = "slug"
