from rest_framework import serializers

from catalog.serializers import ScheduleTitleSerializer

from .models import TelegramNotificationChannel, TitleNotificationSubscription


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramNotificationChannel
        fields = ["username", "is_active", "linked_at", "disabled_at", "last_error"]


class SubscriptionSerializer(serializers.ModelSerializer):
    title = ScheduleTitleSerializer(read_only=True)

    class Meta:
        model = TitleNotificationSubscription
        fields = ["title", "is_active", "created_at", "updated_at"]
