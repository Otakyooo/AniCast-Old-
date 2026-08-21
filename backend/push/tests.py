import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Episode, Title
from push.models import NotificationDelivery, TelegramNotificationChannel, TitleNotificationSubscription
from push.tasks import dispatch_episode_notifications


NOTIFY_SETTINGS = {
    "TELEGRAM_NOTIFY_BOT_TOKEN": "notify-token",
    "TELEGRAM_NOTIFY_BOT_USERNAME": "anicast_push_test_bot",
    "TELEGRAM_NOTIFY_WEBHOOK_SECRET": "notify-secret",
}


def csrf_client(user=None):
    client = APIClient(enforce_csrf_checks=True)
    if user:
        client.force_login(user)
    response = client.get("/api/v1/auth/csrf/")
    return client, response.json()["csrfToken"]


@pytest.fixture
def notification_data(db):
    user = User.objects.create_user(email="notify@example.com", password="A-strong-passphrase-2042")
    title = Title.objects.create(name="Notify Title", slug="notify-title", status="ongoing")
    episode = Episode.objects.create(title=title, number=1, air_date=timezone.localdate())
    return user, title, episode


@override_settings(**NOTIFY_SETTINGS)
@pytest.mark.django_db
def test_notification_bot_challenge_links_channel(notification_data):
    user, _, _ = notification_data
    client, csrf = csrf_client(user)
    challenge = client.post("/api/v1/notifications/telegram/challenge/", HTTP_X_CSRFTOKEN=csrf)
    assert challenge.status_code == 201
    token = challenge.json()["bot_url"].split("start=", 1)[1]
    webhook = APIClient(enforce_csrf_checks=True).post(
        "/api/v1/notifications/telegram/webhook/",
        {"message": {"text": f"/start {token}", "from": {"id": 123, "username": "notify"}, "chat": {"id": 123, "type": "private"}}},
        format="json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="notify-secret",
    )
    assert webhook.status_code == 200
    assert "подключены" in webhook.json()["text"]
    assert client.get("/api/v1/notifications/telegram/channel/").json()["connected"] is True
    assert TelegramNotificationChannel.objects.get().user == user


@override_settings(**NOTIFY_SETTINGS)
@pytest.mark.django_db
def test_notification_webhook_rejects_wrong_secret_and_stop_disables(notification_data):
    user, _, _ = notification_data
    channel = TelegramNotificationChannel.objects.create(user=user, telegram_user_id=123, chat_id=123)
    bad = APIClient().post("/api/v1/notifications/telegram/webhook/", {}, format="json")
    assert bad.status_code == 403
    stopped = APIClient().post(
        "/api/v1/notifications/telegram/webhook/",
        {"message": {"text": "/stop", "from": {"id": 123}, "chat": {"id": 123, "type": "private"}}},
        format="json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="notify-secret",
    )
    assert stopped.status_code == 200
    channel.refresh_from_db()
    assert channel.is_active is False


@pytest.mark.django_db
def test_title_subscriptions_are_private_and_require_csrf(notification_data):
    user, title, _ = notification_data
    anonymous = APIClient()
    assert anonymous.get("/api/v1/notifications/subscriptions/").status_code in {401, 403}
    client = APIClient()
    client.force_login(user)
    assert client.put(f"/api/v1/notifications/subscriptions/{title.slug}/").status_code == 201
    assert client.get("/api/v1/notifications/subscriptions/").json()["count"] == 1
    checked = APIClient(enforce_csrf_checks=True)
    checked.force_login(user)
    assert checked.delete(f"/api/v1/notifications/subscriptions/{title.slug}/").status_code == 403
    assert client.delete(f"/api/v1/notifications/subscriptions/{title.slug}/").status_code == 204


@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
@pytest.mark.django_db
def test_delivery_task_is_idempotent(notification_data, monkeypatch):
    user, title, episode = notification_data
    TelegramNotificationChannel.objects.create(user=user, telegram_user_id=123, chat_id=123)
    TitleNotificationSubscription.objects.create(user=user, title=title)
    sent = []
    monkeypatch.setattr("push.tasks.send_notification", lambda chat_id, text: sent.append((chat_id, text)))
    assert dispatch_episode_notifications()["sent"] == 1
    assert dispatch_episode_notifications()["sent"] == 0
    assert len(sent) == 1
    delivery = NotificationDelivery.objects.get(episode=episode)
    assert delivery.status == NotificationDelivery.Status.SENT
    assert delivery.attempts == 1
