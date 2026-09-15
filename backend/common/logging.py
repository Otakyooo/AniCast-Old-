import json
import logging
from datetime import UTC, datetime


SAFE_FIELDS = (
    "event",
    "request_id",
    "method",
    "endpoint",
    "status_family",
    "duration_ms",
    "dependency",
    "exception_type",
    "task",
    "task_id",
    "result",
    "checked",
    "failed",
    "sent",
    "transitions",
    "source_id",
    "title_id",
    "titles",
    "processed",
    "persisted",
    "scheduled",
    "credits",
    "pages",
    "episodes",
    "named",
    "dated",
    "discovered",
    # NOT "created": logging refuses an extra key that would overwrite an
    # attribute the record already carries, and every LogRecord has a
    # ``created`` timestamp. A counter passed under that name raised
    # KeyError("Attempt to overwrite 'created' in LogRecord") instead of
    # logging, which is what killed the hourly character sync.
    "created_count",
    "linked",
    "pruned",
    "users",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str | int | float] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "service": "backend",
        }
        for field in SAFE_FIELDS:
            value = getattr(record, field, None)
            if isinstance(value, (str, int, float)):
                payload[field] = value
        if record.exc_info and record.exc_info[0]:
            payload["exception_type"] = record.exc_info[0].__name__
        payload.setdefault("event", "log_record")
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
