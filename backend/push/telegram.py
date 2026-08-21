import json
from urllib import request

from django.conf import settings


def send_notification(chat_id: int, text: str) -> None:
    payload = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    req = request.Request(
        f"https://api.telegram.org/bot{settings.TELEGRAM_NOTIFY_BOT_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Telegram returned HTTP {response.status}")
