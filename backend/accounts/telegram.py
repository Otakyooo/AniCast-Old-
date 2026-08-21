import hashlib
import hmac
import re
import time
from collections.abc import Mapping


class TelegramAuthError(ValueError):
    def __init__(self, message: str, code: str = "invalid_telegram_payload"):
        super().__init__(message)
        self.code = code


ALLOWED_FIELDS = {"id", "first_name", "last_name", "username", "photo_url", "auth_date", "hash"}
REQUIRED_FIELDS = {"id", "first_name", "auth_date", "hash"}


def verify_telegram_payload(data: Mapping, bot_token: str, *, now: int | None = None) -> dict:
    if set(data) - ALLOWED_FIELDS or not REQUIRED_FIELDS.issubset(data):
        raise TelegramAuthError("Некорректный набор данных Telegram.")

    telegram_id = data["id"]
    auth_date = data["auth_date"]
    received_hash = data["hash"]
    if isinstance(telegram_id, bool) or not isinstance(telegram_id, int) or not 0 < telegram_id <= 2**52 - 1:
        raise TelegramAuthError("Некорректный идентификатор Telegram.")
    if isinstance(auth_date, bool) or not isinstance(auth_date, int):
        raise TelegramAuthError("Некорректное время авторизации Telegram.")
    if not isinstance(received_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", received_hash):
        raise TelegramAuthError("Некорректная подпись Telegram.")

    limits = {"first_name": 128, "last_name": 128, "username": 128, "photo_url": 2048}
    for field, limit in limits.items():
        value = data.get(field, "")
        if not isinstance(value, str) or len(value) > limit:
            raise TelegramAuthError(f"Некорректное поле {field}.")

    signed = {key: value for key, value in data.items() if key != "hash"}
    check_string = "\n".join(f"{key}={signed[key]}" for key in sorted(signed))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("Telegram не подтвердил данные авторизации.")

    current_time = int(time.time()) if now is None else now
    age = current_time - auth_date
    if age < -30 or age > 300:
        raise TelegramAuthError("Авторизация Telegram устарела.", "telegram_auth_expired")
    return signed
