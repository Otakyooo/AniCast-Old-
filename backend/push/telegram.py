import json
from urllib import request

from django.conf import settings


def send_notification(chat_id: int, text: str) -> None:
    """Send one Bot API message through whatever path can reach Telegram.

    ``TELEGRAM_API_BASE_URL`` exists because api.telegram.org is unreachable from
    MainServer (see docs/OPERATIONS.md): it points at the relay on the VPS, which
    can reach it. The default stays the direct upstream so local development and
    any future host with working egress need no configuration.
    """
    payload = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    base = settings.TELEGRAM_API_BASE_URL.rstrip("/")
    req = request.Request(
        f"{base}/bot{settings.TELEGRAM_NOTIFY_BOT_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Telegram returned HTTP {response.status}")
