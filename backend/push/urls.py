from django.urls import path

from .views import (
    NotificationChallengeView,
    NotificationChannelView,
    SubscriptionListView,
    SubscriptionView,
    notification_webhook,
)

urlpatterns = [
    path("notifications/telegram/challenge/", NotificationChallengeView.as_view(), name="notification-challenge"),
    path("notifications/telegram/channel/", NotificationChannelView.as_view(), name="notification-channel"),
    path("notifications/telegram/webhook/", notification_webhook, name="notification-webhook"),
    path("notifications/subscriptions/", SubscriptionListView.as_view(), name="notification-subscriptions"),
    path("notifications/subscriptions/<slug:slug>/", SubscriptionView.as_view(), name="notification-subscription"),
]
