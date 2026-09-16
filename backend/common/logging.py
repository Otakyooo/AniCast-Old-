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
    # Passed by the account and push tasks but missing here, so the formatter
    # silently dropped them: the call site looked complete and the line was
    # short a field. ``error`` is deliberately absent — it would duplicate
    # ``exception_type``, which every other failure site already uses.
    "kind",
    "attempts",
    "expired",
    "channel",
    # The request path, added by ObservabilityMiddleware. The grouped "endpoint"
    # label keeps metrics cardinality bounded, but a log line that says only
    # "api" cannot tell which route 5xx'd, so the full path rides with the
    # request id.
    "path",
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
            # Without the stack, an ERROR line carried only an exception type name
            # and the actual cause stayed invisible: a failed provider sync was
            # reported as CharacterSyncError with no clue why, and the 5xx that
            # paged at night had no traceback anywhere in the logs. The message
            # itself stays out on purpose -- interpolated call-site text is where
            # a credential could land, and the traceback already carries the
            # exception's own text.
            traceback = self.formatException(record.exc_info)
            if traceback:
                payload["traceback"] = traceback.rstrip("\n")
        payload.setdefault("event", "log_record")
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
