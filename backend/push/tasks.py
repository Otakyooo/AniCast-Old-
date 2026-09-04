from datetime import timedelta
from urllib.error import HTTPError
import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from catalog.models import Episode
from catalog.i18n import translated_value_for_language

from .models import EventNotification, NotificationDelivery, TelegramNotificationChannel, TitleNotificationSubscription
from .telegram import send_notification
from common.metrics import increment

logger = logging.getLogger("anicast.notifications")

SITE_BASE_URL = getattr(settings, "ANICAST_SITE_URL", "https://anicast.online")
MAX_EVENT_ATTEMPTS = 3
DIGEST_MAX_LINES = 25


def title_watch_path(slug: str, episode_number: int) -> str:
    """Return the canonical title-page playback URL for an episode."""
    return f"/titles/{slug}?episode={episode_number}#watch"


@shared_task
def dispatch_episode_notifications():
    if not settings.TELEGRAM_NOTIFY_BOT_TOKEN:
        return {"sent": 0, "failed": 0}
    today = timezone.localdate()
    episodes = Episode.objects.filter(
        air_date__gte=today - timedelta(days=2), air_date__lte=today
    ).select_related("title").prefetch_related("translations", "title__translations")
    sent = failed = 0
    rate_limited = False
    for episode in episodes:
        if rate_limited:
            break
        subscriptions = TitleNotificationSubscription.objects.filter(
            title=episode.title,
            is_active=True,
            user__telegram_notification_channel__is_active=True,
        ).select_related("user__telegram_notification_channel")
        for subscription in subscriptions:
            delivery, _ = NotificationDelivery.objects.get_or_create(subscription=subscription, episode=episode)
            if delivery.status == NotificationDelivery.Status.SENT or delivery.attempts >= 3:
                continue
            channel = subscription.user.telegram_notification_channel
            language = subscription.user.preferred_language
            title_name = translated_value_for_language(episode.title, "name", language)
            episode_name = translated_value_for_language(episode, "name", language)
            watch_url = f"{SITE_BASE_URL}{title_watch_path(episode.title.slug, episode.number)}"
            if language == "en":
                message = (
                    f"New AniCast episode\n\n{title_name} — episode {episode.number}"
                    f"{f' · {episode_name}' if episode_name else ''}\n"
                    f"{watch_url}"
                )
            else:
                message = (
                    f"Новая серия AniCast\n\n{title_name} — серия {episode.number}"
                    f"{f' · {episode_name}' if episode_name else ''}\n"
                    f"{watch_url}"
                )
            delivery.attempts += 1
            send_error: Exception | None = None
            try:
                send_notification(channel.chat_id, message)
            except SoftTimeLimitExceeded:
                # A soft timeout must abort the whole batch instead of being
                # misrecorded as one recipient's delivery failure.
                delivery.status = NotificationDelivery.Status.PENDING
                delivery.save(update_fields=["attempts", "status"])
                raise
            except Exception as exc:
                send_error = exc
                delivery.status = NotificationDelivery.Status.FAILED
                delivery.error = type(send_error).__name__[:500]
                failed += 1
                increment("notification_deliveries", "failed")
                if isinstance(send_error, HTTPError) and send_error.code in {400, 401, 403}:
                    TelegramNotificationChannel.objects.filter(pk=channel.pk).update(
                        is_active=False, disabled_at=timezone.now(), last_error=delivery.error
                    )
            else:
                delivery.status = NotificationDelivery.Status.SENT
                delivery.sent_at = timezone.now()
                delivery.error = ""
                sent += 1
                increment("notification_deliveries", "sent")
            delivery.save(update_fields=["status", "attempts", "error", "sent_at", "updated_at"])
            if isinstance(send_error, HTTPError) and send_error.code == 429:
                # Telegram asked us to slow down: leave this delivery pending
                # for the next beat run instead of hammering through the list.
                delivery.status = NotificationDelivery.Status.PENDING
                delivery.save(update_fields=["status"])
                rate_limited = True
                break
    logger.info("notification batch completed", extra={
        "event": "notification_batch_completed", "sent": sent, "failed": failed,
        **({"aborted": "rate_limited"} if rate_limited else {}),
    })
    return {"sent": sent, "failed": failed}


def event_message(kind: EventNotification.Kind, context: str, url_path: str, language: str) -> str:
    link = f"\n{SITE_BASE_URL}{url_path}" if url_path else ""
    if language == "en":
        texts = {
            EventNotification.Kind.REVIEW_APPROVED: f"Your review of “{context}” has been approved and published.{link}",
            EventNotification.Kind.REVIEW_REJECTED: f"Your review of “{context}” was rejected by a moderator.{link}",
            EventNotification.Kind.REPORT_RESOLVED: f"Your report about the source “{context}” has been resolved.{link}",
            EventNotification.Kind.REPORT_REJECTED: f"Your report about the source “{context}” was reviewed and declined.{link}",
        }
        return f"AniCast update\n\n{texts[kind]}"
    texts = {
        EventNotification.Kind.REVIEW_APPROVED: f"Ваша рецензия на «{context}» одобрена и опубликована.{link}",
        EventNotification.Kind.REVIEW_REJECTED: f"Ваша рецензия на «{context}» отклонена модератором.{link}",
        EventNotification.Kind.REPORT_RESOLVED: f"Ваша жалоба на источник «{context}» решена.{link}",
        EventNotification.Kind.REPORT_REJECTED: f"Ваша жалоба на источник «{context}» рассмотрена и отклонена.{link}",
    }
    return f"Обновление AniCast\n\n{texts[kind]}"


@shared_task
def dispatch_event_notifications():
    if not settings.TELEGRAM_NOTIFY_BOT_TOKEN:
        return {"sent": 0, "failed": 0}
    # FAILED rows stay in the retry window until the attempts cap, matching
    # the episode delivery semantics: transient outages recover on later beats.
    pending = EventNotification.objects.filter(attempts__lt=MAX_EVENT_ATTEMPTS).exclude(
        status__in=[EventNotification.Status.SENT, EventNotification.Status.SKIPPED],
    ).select_related("user__telegram_notification_channel")
    sent = failed = 0
    rate_limited = False
    for notification in pending:
        if rate_limited:
            break
        channel = getattr(notification.user, "telegram_notification_channel", None)
        if channel is None or not channel.is_active:
            notification.status = EventNotification.Status.SKIPPED
            notification.save(update_fields=["status", "updated_at"])
            continue
        message = event_message(
            notification.kind, notification.context, notification.url_path, notification.user.preferred_language,
        )
        notification.attempts += 1
        try:
            send_notification(channel.chat_id, message)
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            notification.status = EventNotification.Status.FAILED
            notification.error = type(exc).__name__[:500]
            failed += 1
            increment("notification_deliveries", "failed")
            if isinstance(exc, HTTPError) and exc.code in {400, 401, 403}:
                TelegramNotificationChannel.objects.filter(pk=channel.pk).update(
                    is_active=False, disabled_at=timezone.now(), last_error=notification.error,
                )
            if isinstance(exc, HTTPError) and exc.code == 429:
                notification.status = EventNotification.Status.PENDING
                notification.save(update_fields=["status", "attempts", "error", "updated_at"])
                rate_limited = True
                break
        else:
            notification.status = EventNotification.Status.SENT
            notification.sent_at = timezone.now()
            notification.error = ""
            sent += 1
            increment("notification_deliveries", "sent")
        notification.save(update_fields=["status", "attempts", "error", "sent_at", "updated_at"])
    logger.info("event notification batch completed", extra={
        "event": "event_notification_batch_completed", "sent": sent, "failed": failed,
        **({"aborted": "rate_limited"} if rate_limited else {}),
    })
    return {"sent": sent, "failed": failed}


def enqueue_event_notification(user, kind: str, context: str = "", url_path: str = "") -> None:
    """Record an outbound one-shot push; the ledger guarantees delivery.

    The immediate dispatch is best-effort so admin actions never fail on a
    missing broker — the beat task picks every PENDING row up anyway.
    """
    EventNotification.objects.create(user=user, kind=kind, context=context[:200], url_path=url_path[:200])
    try:
        dispatch_event_notifications.delay()
    except Exception:
        logger.warning("event notification deferred to beat", extra={"event": "event_dispatch_deferred"}, exc_info=True)


def notify_review_moderated(review) -> None:
    kind = (
        EventNotification.Kind.REVIEW_APPROVED
        if review.status == review.Status.APPROVED
        else EventNotification.Kind.REVIEW_REJECTED
    )
    enqueue_event_notification(
        review.user, kind, context=review.title.name, url_path=f"/titles/{review.title.slug}/?tab=community",
    )


def notify_report_handled(report) -> None:
    kind = (
        EventNotification.Kind.REPORT_RESOLVED
        if report.status == report.Status.RESOLVED
        else EventNotification.Kind.REPORT_REJECTED
    )
    episode = report.source.episode
    enqueue_event_notification(
        report.reporter, kind, context=report.source.name,
        url_path=title_watch_path(episode.title.slug, episode.number),
    )


def digest_message(groups: list[tuple[str, list[int]]], language: str) -> str:
    shown = groups[:DIGEST_MAX_LINES]
    lines = [f"• {name} — {', '.join(str(number) for number in numbers)}" for name, numbers in shown]
    hidden = len(groups) - len(shown)
    if hidden > 0:
        suffix = f" (+{hidden} more)" if language == "en" else f" (ещё +{hidden})"
        lines.append(suffix)
    header = "Today on AniCast" if language == "en" else "Расписание AniCast на сегодня"
    link = f"{SITE_BASE_URL}/schedule"
    return f"{header}\n\n" + "\n".join(lines) + f"\n\n{link}"


@shared_task
def send_schedule_digest():
    if not settings.TELEGRAM_NOTIFY_BOT_TOKEN:
        return {"sent": 0}
    today = timezone.localdate()
    episodes = (
        Episode.objects.filter(air_date=today)
        .select_related("title")
        .prefetch_related("translations", "title__translations")
    )
    if not episodes.exists():
        return {"sent": 0}

    channels = TelegramNotificationChannel.objects.filter(is_active=True, schedule_digest_enabled=True).exclude(
        last_digest_date=today,
    ).select_related("user")
    by_title: dict[int, dict] = {}
    for episode in episodes:
        entry = by_title.setdefault(episode.title_id, {"title": episode.title, "numbers": []})
        entry["numbers"].append(episode.number)

    sent = 0
    for channel in channels:
        language = channel.user.preferred_language
        groups = [
            (translated_value_for_language(entry["title"], "name", language), sorted(entry["numbers"]))
            for entry in by_title.values()
        ]
        groups.sort(key=lambda item: item[0].lower())
        try:
            send_notification(channel.chat_id, digest_message(groups, language))
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            logger.warning("schedule digest failed", extra={
                "event": "schedule_digest_failed", "channel": channel.pk, "error": type(exc).__name__,
            })
            continue
        channel.last_digest_date = today
        channel.save(update_fields=["last_digest_date", "updated_at"])
        sent += 1
    return {"sent": sent}
