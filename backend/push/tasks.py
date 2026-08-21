from urllib.error import HTTPError
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from catalog.models import Episode
from catalog.i18n import translated_value_for_language

from .models import NotificationDelivery, TelegramNotificationChannel, TitleNotificationSubscription
from .telegram import send_notification
from common.metrics import increment

logger = logging.getLogger("anicast.notifications")


@shared_task
def dispatch_episode_notifications():
    if not settings.TELEGRAM_NOTIFY_BOT_TOKEN:
        return {"sent": 0, "failed": 0}
    episodes = Episode.objects.filter(air_date=timezone.localdate()).select_related("title").prefetch_related(
        "translations", "title__translations"
    )
    sent = failed = 0
    for episode in episodes:
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
            if language == "en":
                message = (
                    f"New AniCast episode\n\n{title_name} — episode {episode.number}"
                    f"{f' · {episode_name}' if episode_name else ''}\n"
                    f"https://anicast.online/titles/{episode.title.slug}/episodes/{episode.number}"
                )
            else:
                message = (
                    f"Новый эпизод AniCast\n\n{title_name} — эпизод {episode.number}"
                    f"{f' · {episode_name}' if episode_name else ''}\n"
                    f"https://anicast.online/titles/{episode.title.slug}/episodes/{episode.number}"
                )
            delivery.attempts += 1
            try:
                send_notification(channel.chat_id, message)
            except Exception as error:
                delivery.status = NotificationDelivery.Status.FAILED
                delivery.error = type(error).__name__[:500]
                failed += 1
                increment("notification_deliveries", "failed")
                if isinstance(error, HTTPError) and error.code in {400, 403}:
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
    logger.info("notification batch completed", extra={
        "event": "notification_batch_completed", "sent": sent, "failed": failed,
    })
    return {"sent": sent, "failed": failed}
