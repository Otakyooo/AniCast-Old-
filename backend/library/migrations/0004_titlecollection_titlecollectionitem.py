from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_user_public_id"),
        ("catalog", "0009_provider_playback_adapter_provider_playback_config"),
        ("library", "0003_titlenote"),
    ]
    operations = [
        migrations.CreateModel(
            name="TitleCollection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=80)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("is_public", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="title_collections", to="accounts.user")),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
                "constraints": [models.UniqueConstraint(fields=("owner", "slug"), name="unique_owner_collection_slug")],
            },
        ),
        migrations.CreateModel(
            name="TitleCollectionItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("collection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="library.titlecollection")),
                ("title", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="collection_items", to="catalog.title")),
            ],
            options={
                "ordering": ["position", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("collection", "title"), name="unique_collection_title"),
                    models.UniqueConstraint(fields=("collection", "position"), name="unique_collection_position"),
                ],
            },
        ),
    ]
