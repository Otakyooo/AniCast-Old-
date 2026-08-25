from django.db import models


class AvailabilitySample(models.Model):
    """One availability probe outcome for a monitored target.

    Written by ``common.tasks.probe_site_availability`` once a minute per
    target; the staff dashboard and Prometheus gauges aggregate these rows,
    so nothing else needs to persist uptime state.
    """

    class Target(models.TextChoices):
        SITE = "site", "Сайт"
        API = "api", "API каталога"
        READINESS = "readiness", "Readiness backend"

    target = models.CharField(max_length=16, choices=Target.choices, db_index=True)
    checked_at = models.DateTimeField(db_index=True)
    ok = models.BooleanField()
    latency_ms = models.PositiveIntegerField(default=0)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    detail = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = "Проба доступности"
        verbose_name_plural = "Пробы доступности"
        ordering = ["-checked_at"]
        indexes = [models.Index(fields=["target", "checked_at"])]

    def __str__(self) -> str:
        state = "ok" if self.ok else f"fail ({self.detail})" if self.detail else "fail"
        return f"{self.target} {state} @ {self.checked_at:%Y-%m-%d %H:%M:%S}"
