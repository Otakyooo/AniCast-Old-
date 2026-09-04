from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    # Boolean rather than the timestamp: the client only ever asks whether the
    # address is proven, and the exact moment is staff-facing data.
    email_verified = serializers.SerializerMethodField()
    has_password = serializers.SerializerMethodField()

    def get_avatar_url(self, obj):
        identity = obj.external_identities.exclude(avatar_url="").order_by("id").first()
        return identity.avatar_url if identity else ""

    def get_email_verified(self, obj) -> bool:
        return obj.email_verified_at is not None

    def get_has_password(self, obj) -> bool:
        # Telegram-only accounts are created with an unusable password, so the
        # settings screen must offer "set a password", not "change" — and the
        # change form must not ask for a current password that cannot exist.
        return obj.has_usable_password()

    class Meta:
        model = User
        fields = [
            "id", "public_id", "email", "email_verified", "has_password", "display_name", "bio",
            "profile_is_public", "preferred_language", "date_joined", "avatar_url",
        ]


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["preferred_language"]


class PublicProfileUpdateSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(max_length=80, allow_blank=True, trim_whitespace=True)
    bio = serializers.CharField(max_length=280, allow_blank=True, trim_whitespace=True)

    class Meta:
        model = User
        fields = ["display_name", "bio", "profile_is_public"]

    def validate(self, attrs):
        if attrs.get("profile_is_public") and not attrs.get("display_name", "").strip():
            raise serializers.ValidationError({"display_name": "Укажите имя перед публикацией профиля."})
        return attrs


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    display_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        email = User.objects.normalize_email(value).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Аккаунт с таким email уже существует.")
        return email

    def validate(self, attrs):
        candidate = User(email=attrs["email"], display_name=attrs.get("display_name", ""))
        password_validation.validate_password(attrs["password"], candidate)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            email=attrs["email"].lower(),
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError("Неверный email или пароль.")
        if not user.is_active:
            raise serializers.ValidationError("Аккаунт отключён.")
        attrs["user"] = user
        return attrs


class EmailRequestSerializer(serializers.Serializer):
    """Address for a reset request. Whether it exists is never revealed."""

    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        return User.objects.normalize_email(value).lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=64, trim_whitespace=True)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    """Change the password of the signed-in account.

    ``current_password`` is required whenever the account has a usable one: a
    stolen session must not be enough to take the account over permanently.
    Telegram-only accounts have no password to prove, so for them this sets the
    first one — and they have a proven Telegram identity instead.
    """

    current_password = serializers.CharField(
        max_length=128, write_only=True, required=False, allow_blank=True, trim_whitespace=False,
    )
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["user"]
        if user.has_usable_password():
            current = attrs.get("current_password") or ""
            if not user.check_password(current):
                raise serializers.ValidationError({"current_password": "Неверный текущий пароль."})
        password_validation.validate_password(attrs["password"], user)
        if user.check_password(attrs["password"]):
            raise serializers.ValidationError({"password": "Новый пароль совпадает с текущим."})
        return attrs
