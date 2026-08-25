from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Episode, EpisodeTranslation, Source, SourceReport, Title, TitleTranslation
from community.models import TitleReview
from push.models import (
    EventNotification,
    NotificationDelivery,
    TelegramNotificationChannel,
    TitleNotificationSubscription,
)
from push.tasks import dispatch_episode_notifications, dispatch_event_notifications, send_schedule_digest


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


@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
@pytest.mark.django_db
def test_delivery_uses_user_language_and_content_translation(notification_data, monkeypatch):
    user, title, episode = notification_data
    user.preferred_language = "en"
    user.save(update_fields=["preferred_language"])
    TitleTranslation.objects.create(title=title, language="en", name="English title")
    EpisodeTranslation.objects.create(episode=episode, language="en", name="English episode")
    TelegramNotificationChannel.objects.create(user=user, telegram_user_id=456, chat_id=456)
    TitleNotificationSubscription.objects.create(user=user, title=title)
    sent = []
    monkeypatch.setattr("push.tasks.send_notification", lambda chat_id, text: sent.append(text))
    dispatch_episode_notifications()
    assert "New AniCast episode" in sent[0]
    assert "English title" in sent[0]
    assert "English episode" in sent[0]


@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
@pytest.mark.django_db
def test_delivery_catches_up_recent_episodes_but_not_future(notification_data, monkeypatch):
    user, title, episode = notification_data
    Episode.objects.create(title=title, number=2, air_date=timezone.localdate() - timedelta(days=1))
    Episode.objects.create(title=title, number=3, air_date=timezone.localdate() + timedelta(days=1))
    TelegramNotificationChannel.objects.create(user=user, telegram_user_id=123, chat_id=123)
    TitleNotificationSubscription.objects.create(user=user, title=title)
    sent = []
    monkeypatch.setattr("push.tasks.send_notification", lambda chat_id, text: sent.append(text))
    result = dispatch_episode_notifications()
    assert result["sent"] == 2
    assert len(sent) == 2


@pytest.mark.django_db
def test_delivery_list_is_private_and_shaped(notification_data):
    user, title, episode = notification_data
    other = User.objects.create_user(email="other@example.com", password="A-strong-passphrase-2042")
    other_title = Title.objects.create(name="Other Title", slug="other-title", status="ongoing")
    other_episode = Episode.objects.create(title=other_title, number=1, air_date=timezone.localdate())
    subscription = TitleNotificationSubscription.objects.create(user=user, title=title)
    other_subscription = TitleNotificationSubscription.objects.create(user=other, title=other_title)
    NotificationDelivery.objects.create(subscription=subscription, episode=episode, status="sent", sent_at=timezone.now())
    NotificationDelivery.objects.create(subscription=other_subscription, episode=other_episode, status="sent")
    client = APIClient()
    client.force_login(user)
    response = client.get("/api/v1/notifications/deliveries/")
    assert response.status_code == 200
    results = response.json()["results"]
    assert response.json()["count"] == 1
    assert results[0]["title"]["slug"] == title.slug
    assert results[0]["episode_number"] == 1
    assert results[0]["status"] == "sent"
    assert APIClient().get("/api/v1/notifications/deliveries/").status_code in {401, 403}


def make_review(user, title, status=TitleReview.Status.PENDING):
    return TitleReview.objects.create(user=user, title=title, body="Отличный сериал на все времена.", status=status)


def make_report(user, episode, status=SourceReport.Status.NEW):
    source = Source.objects.create(
        episode=episode, name="Test Provider", kind="sub", url="https://provider.example/watch/1",
    )
    return SourceReport.objects.create(source=source, reporter=user, reason=SourceReport.Reason.UNAVAILABLE, status=status)


@pytest.mark.django_db
@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
def test_event_notification_skips_users_without_channel(monkeypatch):
    user = User.objects.create_user(email="quiet@example.com", password="A-strong-passphrase-2042")
    EventNotification.objects.create(user=user, kind=EventNotification.Kind.REVIEW_APPROVED)
    sent = []
    monkeypatch.setattr("push.tasks.send_notification", lambda chat_id, text: sent.append(text))
    dispatch_event_notifications()
    notification = EventNotification.objects.get()
    assert notification.status == EventNotification.Status.SKIPPED
    assert sent == []


@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
@pytest.mark.django_db
def test_event_notification_sends_in_user_language(monkeypatch):
    user = User.objects.create_user(email="author@example.com", password="A-strong-passphrase-2042", preferred_language="en")
    title = Title.objects.create(name="Русское имя", slug="ru-name", status="ongoing")
    TelegramNotificationChannel.objects.create(user=user, telegram_user_id=1, chat_id=11)
    sent = []
    monkeypatch.setattr("push.tasks.send_notification", lambda chat_id, text: sent.append((chat_id, text)))
    EventNotification.objects.create(
        user=user, kind=EventNotification.Kind.REVIEW_APPROVED, context=title.name, url_path=f"/titles/{title.slug}/?tab=community",
    )
    dispatch_event_notifications()
    assert len(sent) == 1
    assert sent[0][0] == 11
    assert "approved and published" in sent[0][1]
    assert "Русское имя" in sent[0][1]
    assert "https://anicast.online/titles/ru-name/" in sent[0][1]
    notification = EventNotification.objects.get()
    assert notification.status == EventNotification.Status.SENT
    assert notification.attempts == 1


@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
@pytest.mark.django_db
def test_event_notification_retries_failures_then_stops(monkeypatch):
    user = User.objects.create_user(email="retry@example.com", password="A-strong-passphrase-2042")
    TelegramNotificationChannel.objects.create(user=user, telegram_user_id=2, chat_id=22)
    calls = []

    def fail(chat_id, text):
        calls.append(1)
        raise RuntimeError("telegram down")

    monkeypatch.setattr("push.tasks.send_notification", fail)
    EventNotification.objects.create(user=user, kind=EventNotification.Kind.REPORT_RESOLVED)
    for _ in range(3):
        dispatch_event_notifications()
    notification = EventNotification.objects.get()
    assert notification.status == EventNotification.Status.FAILED
    assert notification.attempts == 3
    assert len(calls) == 3


@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
@pytest.mark.django_db
def test_event_notification_disables_channel_on_auth_error(monkeypatch):
    from urllib.error import HTTPError

    user = User.objects.create_user(email="dead@example.com", password="A-strong-passphrase-2042")
    channel = TelegramNotificationChannel.objects.create(user=user, telegram_user_id=3, chat_id=33)
    error = HTTPError("https://api.telegram.org", 403, "blocked", None, None)

    def raise_blocked(chat_id, text):
        raise error

    monkeypatch.setattr("push.tasks.send_notification", raise_blocked)
    EventNotification.objects.create(user=user, kind=EventNotification.Kind.REVIEW_REJECTED)
    dispatch_event_notifications()
    channel.refresh_from_db()
    assert channel.is_active is False
    notification = EventNotification.objects.get()
    assert notification.status == EventNotification.Status.FAILED


@pytest.mark.django_db
def test_review_moderation_enqueues_once_per_state_change(notification_data, monkeypatch):
    from django.contrib import admin as django_admin

    user, title, _ = notification_data
    review = make_review(user, title)
    deferred = []
    monkeypatch.setattr("push.tasks.dispatch_event_notifications.delay", lambda: deferred.append(True))

    class FakeRequest:
        user = User.objects.create_user(email="staffer@example.com", password="A-strong-passphrase-2042")

    from community.admin import ReviewAdmin
    from community.models import TitleReview as Review

    admin_instance = ReviewAdmin(Review, django_admin.site)
    admin_instance.message_user = lambda *args, **kwargs: None
    admin_instance.set_status(FakeRequest(), TitleReview.objects.filter(pk=review.pk), Review.Status.APPROVED)
    admin_instance.set_status(FakeRequest(), TitleReview.objects.filter(pk=review.pk), Review.Status.APPROVED)
    events = EventNotification.objects.all()
    assert events.count() == 1
    assert events.get().kind == EventNotification.Kind.REVIEW_APPROVED
    assert deferred == [True]
    admin_instance.set_status(FakeRequest(), TitleReview.objects.filter(pk=review.pk), Review.Status.REJECTED)
    kinds = list(EventNotification.objects.order_by("id").values_list("kind", flat=True))
    assert kinds == [EventNotification.Kind.REVIEW_APPROVED, EventNotification.Kind.REVIEW_REJECTED]


@pytest.mark.django_db
def test_report_final_status_notifies_but_reviewing_is_silent(notification_data, monkeypatch):
    from django.contrib import admin as django_admin

    user, _, episode = notification_data
    report = make_report(user, episode)
    monkeypatch.setattr("push.tasks.dispatch_event_notifications.delay", lambda: None)

    class FakeRequest:
        user = User.objects.create_user(email="staffer@example.com", password="A-strong-passphrase-2042")

    from catalog.admin import SourceReportAdmin
    from catalog.models import SourceReport as Report

    admin_instance = SourceReportAdmin(Report, django_admin.site)
    admin_instance.message_user = lambda *args, **kwargs: None
    queryset = Report.objects.filter(pk=report.pk)
    admin_instance.set_status(FakeRequest(), queryset, Report.Status.REVIEWING)
    assert EventNotification.objects.count() == 0
    admin_instance.set_status(FakeRequest(), queryset, Report.Status.RESOLVED)
    admin_instance.set_status(FakeRequest(), queryset, Report.Status.RESOLVED)
    events = EventNotification.objects.all()
    assert events.count() == 1
    assert events.get().kind == EventNotification.Kind.REPORT_RESOLVED
    assert f"/episodes/{episode.number}/" in events.get().url_path


@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
@pytest.mark.django_db
def test_schedule_digest_sends_grouped_message_once_a_day(notification_data, monkeypatch):
    user, title, episode = notification_data
    Episode.objects.create(title=title, number=2, air_date=timezone.localdate())
    other_title = Title.objects.create(name="Другой тайтл", slug="other-digest", status="ongoing")
    Episode.objects.create(title=other_title, number=5, air_date=timezone.localdate())
    Episode.objects.create(title=title, number=9, air_date=timezone.localdate() + timedelta(days=1))
    channel = TelegramNotificationChannel.objects.create(user=user, telegram_user_id=7, chat_id=77)
    sent = []
    monkeypatch.setattr("push.tasks.send_notification", lambda chat_id, text: sent.append((chat_id, text)))

    assert send_schedule_digest()["sent"] == 0  # opt-in flag is off by default
    channel.schedule_digest_enabled = True
    channel.save(update_fields=["schedule_digest_enabled"])
    assert send_schedule_digest()["sent"] == 1
    text = sent[0][1]
    assert "Расписание AniCast на сегодня" in text
    assert "Notify Title — 1, 2" in text
    assert "Другой тайтл — 5" in text
    assert "9" not in text.split("\n")[2]  # tomorrow's episode stays out
    # The same-day rerun must be a no-op.
    assert send_schedule_digest()["sent"] == 0
    channel.refresh_from_db()
    assert channel.last_digest_date == timezone.localdate()


@override_settings(TELEGRAM_NOTIFY_BOT_TOKEN="notify-token")
@pytest.mark.django_db
def test_schedule_digest_handles_empty_day_and_failure(notification_data, monkeypatch):
    user, _, episode = notification_data
    episode.air_date = timezone.localdate() + timedelta(days=3)
    episode.save(update_fields=["air_date"])
    TelegramNotificationChannel.objects.create(user=user, telegram_user_id=8, chat_id=88, schedule_digest_enabled=True)
    assert send_schedule_digest()["sent"] == 0

    episode.air_date = timezone.localdate()
    episode.save(update_fields=["air_date"])

    def fail(chat_id, text):
        raise RuntimeError("telegram down")

    monkeypatch.setattr("push.tasks.send_notification", fail)
    assert send_schedule_digest()["sent"] == 0
    # A failed delivery leaves the day unmarked so the next beat run retries.
    assert not TelegramNotificationChannel.objects.get().last_digest_date


@pytest.mark.django_db
def test_channel_digest_toggle_requires_boolean_and_auth(notification_data):
    user, _, _ = notification_data
    TelegramNotificationChannel.objects.create(user=user, telegram_user_id=9, chat_id=99)
    anonymous = APIClient()
    assert anonymous.patch("/api/v1/notifications/telegram/channel/", {}, format="json").status_code in {401, 403}
    client = APIClient()
    client.force_login(user)
    bad = client.patch("/api/v1/notifications/telegram/channel/", {"schedule_digest_enabled": "yes"}, format="json")
    assert bad.status_code == 400
    ok = client.patch("/api/v1/notifications/telegram/channel/", {"schedule_digest_enabled": True}, format="json")
    assert ok.status_code == 200
    assert ok.json()["schedule_digest_enabled"] is True
    listing = client.get("/api/v1/notifications/telegram/channel/").json()
    assert listing["channel"]["schedule_digest_enabled"] is True
