from django.contrib import admin
from django.utils import timezone

from .models import TitleRating, TitleReview


@admin.register(TitleRating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["user", "title", "value", "updated_at"]
    list_filter = ["value", "updated_at"]
    search_fields = ["user__email", "user__display_name", "title__name"]
    readonly_fields = ["user", "title", "value", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TitleReview)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["user", "title", "status", "contains_spoilers", "created_at", "moderated_by"]
    list_filter = ["status", "contains_spoilers", "created_at"]
    search_fields = ["user__email", "user__display_name", "title__name", "body"]
    readonly_fields = ["user", "title", "body", "contains_spoilers", "created_at", "updated_at", "moderated_by", "moderated_at", "published_at"]
    actions = ["approve_reviews", "reject_reviews"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def set_status(self, request, queryset, status):
        now = timezone.now()
        for review in queryset:
            review.status = status
            review.moderated_by = request.user
            review.moderated_at = now
            review.published_at = now if status == TitleReview.Status.APPROVED else None
            review.save(update_fields=["status", "moderated_by", "moderated_at", "published_at", "updated_at"])
            self.log_change(request, review, f"Рецензия: {review.get_status_display()}.")

    @admin.action(description="Одобрить рецензии")
    def approve_reviews(self, request, queryset):
        self.set_status(request, queryset, TitleReview.Status.APPROVED)

    @admin.action(description="Отклонить рецензии")
    def reject_reviews(self, request, queryset):
        self.set_status(request, queryset, TitleReview.Status.REJECTED)
