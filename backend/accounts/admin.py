from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AccountEmail, AccountToken, ExternalIdentity, TelegramLoginChallenge, User


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
    list_display = ["email", "display_name", "email_verified_at", "profile_is_public", "preferred_language", "is_staff", "is_active", "date_joined"]
    list_filter = ["profile_is_public", "is_staff", "is_active", "is_superuser", "date_joined"]
    search_fields = ["email", "display_name", "public_id", "external_identities__username", "external_identities__subject"]
    readonly_fields = ["public_id", "email_verified_at"]
    fieldsets = [
        (None, {"fields": ["email", "email_verified_at", "password"]}),
        ("Профиль", {"fields": ["public_id", "display_name", "bio", "profile_is_public", "first_name", "last_name", "preferred_language"]}),
        ("Доступ", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Даты", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "display_name", "bio", "profile_is_public", "preferred_language", "password1", "password2", "is_staff", "is_active"]}),
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


@admin.register(AccountEmail)
class AccountEmailAdmin(admin.ModelAdmin):
    """Read-only view of the mail ledger — the answer to "did the link go out?".

    Nothing here is editable: retries belong to the beat task, and re-sending
    from the admin would mint a second live link for the same account.
    """

    list_display = ["to_address", "kind", "status", "attempts", "created_at", "sent_at", "error"]
    list_filter = ["kind", "status", "created_at"]
    search_fields = ["to_address", "user__email", "user__display_name"]
    readonly_fields = [field.name for field in AccountEmail._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccountToken)
class AccountTokenAdmin(admin.ModelAdmin):
    """Audit trail of issued links. The secret itself is never stored."""

    list_display = ["id", "user", "purpose", "email", "created_at", "expires_at", "consumed_at"]
    list_filter = ["purpose", "created_at"]
    search_fields = ["email", "user__email", "user__display_name"]
    readonly_fields = [field.name for field in AccountToken._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and super().has_change_permission(request, obj)
