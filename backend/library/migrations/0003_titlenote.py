from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0004_provider_rightsgrant_source_provider"),
        ("library", "0002_episodeprogress"),
    ]
    operations = [
        migrations.CreateModel(
            name="TitleNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.CharField(max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_notes", to="catalog.title")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="title_notes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
                "indexes": [models.Index(fields=["user", "updated_at"], name="library_tit_user_id_a52bc0_idx")],
                "constraints": [models.UniqueConstraint(fields=("user", "title"), name="unique_user_title_note")],
            },
        ),
    ]
