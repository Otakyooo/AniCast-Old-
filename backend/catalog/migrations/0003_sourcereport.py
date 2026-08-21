from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0002_alter_franchise_options_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="SourceReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(choices=[("unavailable", "Источник не открывается"), ("wrong_content", "Неверный эпизод или контент"), ("geo_blocked", "Недоступно в регионе"), ("quality", "Проблема качества"), ("other", "Другое")], max_length=32)),
                ("message", models.CharField(blank=True, max_length=500)),
                ("status", models.CharField(choices=[("new", "Новая"), ("reviewing", "На проверке"), ("resolved", "Решена"), ("rejected", "Отклонена")], default="new", max_length=16)),
                ("resolution_note", models.CharField(blank=True, max_length=500)),
                ("handled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("handled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="handled_source_reports", to=settings.AUTH_USER_MODEL)),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="source_reports", to=settings.AUTH_USER_MODEL)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="catalog.source")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["status", "created_at"], name="catalog_sou_status_079218_idx")],
                "constraints": [models.UniqueConstraint(condition=models.Q(("status__in", ["new", "reviewing"])), fields=("source", "reporter", "reason"), name="unique_open_source_report")],
            },
        ),
    ]
