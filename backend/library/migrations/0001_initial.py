from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0002_alter_franchise_options_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="LibraryEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("planned", "Запланировано"), ("watching", "Смотрю"), ("completed", "Просмотрено"), ("on_hold", "Отложено"), ("dropped", "Брошено")], default="planned", max_length=16)),
                ("is_favorite", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="library_entries", to="catalog.title")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="library_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
                "indexes": [models.Index(fields=["user", "status"], name="library_lib_user_id_94ed00_idx"), models.Index(fields=["user", "is_favorite"], name="library_lib_user_id_f0aee9_idx")],
                "constraints": [models.UniqueConstraint(fields=("user", "title"), name="unique_user_library_title")],
            },
        ),
    ]
