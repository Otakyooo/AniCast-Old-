from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "display_name", "preferred_language"]


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["preferred_language"]


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    display_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

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
    password = serializers.CharField(write_only=True, trim_whitespace=False)

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
