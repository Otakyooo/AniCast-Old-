from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0002_alter_franchise_options_and_more"),
        ("library", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="EpisodeProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_watched", models.BooleanField(default=False)),
                ("last_opened_at", models.DateTimeField()),
                ("watched_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("episode", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_progress", to="catalog.episode")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="episode_progress", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-last_opened_at", "-id"],
                "indexes": [models.Index(fields=["user", "last_opened_at"], name="library_epi_user_id_c0dff0_idx")],
                "constraints": [models.UniqueConstraint(fields=("user", "episode"), name="unique_user_episode_progress")],
            },
        ),
    ]
