from rest_framework import serializers

from catalog.serializers import ScheduleTitleSerializer

from .models import NotificationDelivery, TelegramNotificationChannel, TitleNotificationSubscription


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramNotificationChannel
        fields = ["username", "is_active", "linked_at", "disabled_at", "last_error"]


class SubscriptionSerializer(serializers.ModelSerializer):
    title = ScheduleTitleSerializer(read_only=True)

    class Meta:
        model = TitleNotificationSubscription
        fields = ["title", "is_active", "created_at", "updated_at"]


class DeliverySerializer(serializers.ModelSerializer):
    title = ScheduleTitleSerializer(source="episode.title", read_only=True)
    episode_number = serializers.IntegerField(source="episode.number", read_only=True)

    class Meta:
        model = NotificationDelivery
        fields = ["title", "episode_number", "status", "sent_at", "created_at"]
