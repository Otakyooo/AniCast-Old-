from django.conf import settings
from django.db import migrations, models
from django.utils.text import slugify
import django.db.models.deletion


def backfill_providers(apps, schema_editor):
    Provider = apps.get_model("catalog", "Provider")
    Source = apps.get_model("catalog", "Source")
    for name in Source.objects.order_by().values_list("name", flat=True).distinct():
        base = slugify(name) or "provider"
        slug = base
        suffix = 2
        while Provider.objects.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        provider, _ = Provider.objects.get_or_create(name=name, defaults={"slug": slug, "is_enabled": False})
        Source.objects.filter(name=name, provider__isnull=True).update(provider=provider)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0003_sourcereport"),
    ]
    operations = [
        migrations.CreateModel(
            name="Provider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(max_length=140, unique=True)),
                ("website_url", models.URLField(blank=True)),
                ("allowed_hosts", models.JSONField(blank=True, default=list)),
                ("is_enabled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="source",
            name="provider",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sources", to="catalog.provider"),
        ),
        migrations.CreateModel(
            name="RightsGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("draft", "Черновик"), ("active", "Активно"), ("revoked", "Отозвано")], default="draft", max_length=16)),
                ("valid_from", models.DateTimeField()),
                ("valid_until", models.DateTimeField()),
                ("contract_reference", models.CharField(max_length=200)),
                ("notes", models.TextField(blank=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="approved_rights_grants", to=settings.AUTH_USER_MODEL)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rights_grants", to="catalog.source")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "constraints": [models.CheckConstraint(condition=models.Q(("valid_until__gt", models.F("valid_from"))), name="rights_grant_valid_interval"), models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("source",), name="one_active_grant_per_source")],
            },
        ),
        migrations.RunPython(backfill_providers, migrations.RunPython.noop),
    ]
