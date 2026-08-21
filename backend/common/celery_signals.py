import logging
import time

from celery.signals import task_failure, task_postrun, task_prerun, task_retry

from .metrics import TASKS, increment

logger = logging.getLogger("anicast.celery")
_started: dict[str, float] = {}


def _task_name(name: str | None) -> str:
    return name if name in TASKS else "other"


@task_prerun.connect
def task_started(task_id=None, task=None, **kwargs) -> None:
    if task_id:
        _started[task_id] = time.monotonic()


@task_postrun.connect
def task_finished(task_id=None, task=None, state=None, **kwargs) -> None:
    name = _task_name(getattr(task, "name", None))
    result = "success" if state == "SUCCESS" else "failure"
    increment("celery_tasks", name, result)
    duration_ms = round((time.monotonic() - _started.pop(task_id, time.monotonic())) * 1000)
    logger.info("celery task completed", extra={
        "event": "celery_task_completed", "task": name, "task_id": task_id or "", "result": result,
        "duration_ms": max(duration_ms, 0),
    })


@task_failure.connect
def task_failed(task_id=None, exception=None, sender=None, **kwargs) -> None:
    logger.error("celery task failed", extra={
        "event": "celery_task_failed", "task": _task_name(getattr(sender, "name", None)),
        "task_id": task_id or "", "exception_type": type(exception).__name__,
    })


@task_retry.connect
def task_retried(request=None, **kwargs) -> None:
    increment("celery_tasks", _task_name(getattr(request, "task", None)), "retry")
