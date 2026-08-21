from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_provider_rightsgrant_source_provider")]
    operations = [
        migrations.AddField(model_name="source", name="consecutive_failures", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="source", name="last_checked_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="source", name="last_http_status", field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.CreateModel(
            name="SourceHealthCheck",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("checked_at", models.DateTimeField(auto_now_add=True)), ("is_healthy", models.BooleanField()),
                ("http_status", models.PositiveSmallIntegerField(blank=True, null=True)), ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("error", models.CharField(blank=True, max_length=500)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="health_checks", to="catalog.source")),
            ],
            options={"ordering": ["-checked_at", "-id"], "indexes": [models.Index(fields=["source", "checked_at"], name="catalog_sou_source__22921c_idx")]},
        ),
    ]
