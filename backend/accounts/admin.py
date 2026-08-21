from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import ExternalIdentity, TelegramLoginChallenge, User


class ExternalIdentityInline(admin.TabularInline):
    model = ExternalIdentity
    fields = ("provider", "subject", "username", "display_name", "last_authenticated_at")
    readonly_fields = ("provider", "subject", "username", "display_name", "last_authenticated_at")
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ["email", "id"]
    list_display = ["email", "display_name", "preferred_language", "is_staff", "is_active", "date_joined"]
    list_filter = ["is_staff", "is_active", "is_superuser", "date_joined"]
    search_fields = ["email", "display_name", "external_identities__username", "external_identities__subject"]
    readonly_fields = ["public_id"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Профиль", {"fields": ["public_id", "display_name", "first_name", "last_name", "preferred_language"]}),
        ("Доступ", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Даты", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "display_name", "preferred_language", "password1", "password2", "is_staff", "is_active"]}),
    ]
    filter_horizontal = ["groups", "user_permissions"]
    inlines = [ExternalIdentityInline]


@admin.register(ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = ["provider", "subject", "username", "user", "last_authenticated_at"]
    list_filter = ["provider"]
    search_fields = ["subject", "username", "display_name", "user__email"]
    readonly_fields = [
        "user", "provider", "subject", "username", "display_name", "avatar_url",
        "created_at", "updated_at", "last_authenticated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TelegramLoginChallenge)
class TelegramLoginChallengeAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "user", "created_at", "expires_at", "approved_at", "consumed_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["user__email", "user__display_name"]
    readonly_fields = [
        "token_hash", "session_hash", "status", "user", "expires_at",
        "approved_at", "consumed_at", "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False
