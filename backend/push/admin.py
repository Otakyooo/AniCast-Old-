from django.contrib import admin

from .models import (
    NotificationDelivery,
    TelegramNotificationChallenge,
    TelegramNotificationChannel,
    TitleNotificationSubscription,
)


@admin.register(TelegramNotificationChannel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ["user", "username", "chat_id", "is_active", "linked_at", "disabled_at"]
    list_filter = ["is_active", "linked_at"]
    search_fields = ["user__email", "user__display_name", "username", "chat_id"]
    readonly_fields = ["user", "telegram_user_id", "chat_id", "username", "linked_at", "updated_at", "last_error"]

    def has_add_permission(self, request):
        return False


@admin.register(TitleNotificationSubscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "title", "is_active", "updated_at"]
    list_filter = ["is_active", "updated_at"]
    search_fields = ["user__email", "user__display_name", "title__name"]
    readonly_fields = ["user", "title", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False


@admin.register(NotificationDelivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ["subscription", "episode", "status", "attempts", "created_at", "sent_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["subscription__user__email", "episode__title__name"]
    readonly_fields = [field.name for field in NotificationDelivery._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TelegramNotificationChallenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "created_at", "expires_at", "consumed_at"]
    readonly_fields = [field.name for field in TelegramNotificationChallenge._meta.fields]

    def has_add_permission(self, request):
        return False
