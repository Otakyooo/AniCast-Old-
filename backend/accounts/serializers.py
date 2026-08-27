from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj):
        identity = obj.external_identities.exclude(avatar_url="").order_by("id").first()
        return identity.avatar_url if identity else ""

    class Meta:
        model = User
        fields = [
            "id", "public_id", "email", "display_name", "bio", "profile_is_public",
            "preferred_language", "date_joined", "avatar_url",
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
