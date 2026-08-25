from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("catalog", "0012_source_external_id")]

    operations = [
        migrations.AddField(
            model_name="title",
            name="duration_minutes",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="provider",
            name="rights_reference",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="provider",
            name="rights_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="provider",
            name="rights_valid_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="Creator",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, unique=True)),
                ("slug", models.SlugField(max_length=220, unique=True)),
            ],
            options={"verbose_name": "Автор", "verbose_name_plural": "Авторы", "ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="TitleCredit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("director", "Режиссёр"), ("producer", "Продюсер"), ("writer", "Сценарист"), ("composer", "Композитор"), ("designer", "Дизайнер")], max_length=20)),
                ("source", models.CharField(default="manual", max_length=32)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("creator", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="title_credits", to="catalog.creator")),
                ("title", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="credits", to="catalog.title")),
            ],
            options={"verbose_name": "Автор тайтла", "verbose_name_plural": "Авторы тайтла", "ordering": ["sort_order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="titlecredit",
            constraint=models.UniqueConstraint(fields=("title", "creator", "role"), name="unique_title_creator_role"),
        ),
    ]
