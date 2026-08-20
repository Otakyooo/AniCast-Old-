from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Franchise",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, unique=True)),
                ("slug", models.SlugField(max_length=220, unique=True)),
                ("description", models.TextField(blank=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Genre",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(max_length=100, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Title",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=240)),
                ("slug", models.SlugField(max_length=260, unique=True)),
                ("original_name", models.CharField(blank=True, max_length=240)),
                ("synopsis", models.TextField(blank=True)),
                ("title_type", models.CharField(choices=[("anime", "Anime"), ("movie", "Movie"), ("ova", "OVA"), ("special", "Special")], default="anime", max_length=20)),
                ("status", models.CharField(choices=[("ongoing", "Ongoing"), ("finished", "Finished"), ("planned", "Planned")], default="planned", max_length=20)),
                ("year", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("poster_url", models.URLField(blank=True)),
                ("franchise", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="titles", to="catalog.franchise")),
                ("genres", models.ManyToManyField(blank=True, related_name="titles", to="catalog.genre")),
            ],
            options={"ordering": ["name"], "indexes": [models.Index(fields=["status"], name="catalog_ti_status_4d77e1_idx"), models.Index(fields=["title_type"], name="catalog_ti_title_t_ef7d7b_idx")]},
        ),
        migrations.CreateModel(
            name="Episode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField()),
                ("name", models.CharField(blank=True, max_length=240)),
                ("synopsis", models.TextField(blank=True)),
                ("air_date", models.DateField(blank=True, null=True)),
                ("title", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="episodes", to="catalog.title")),
            ],
            options={"ordering": ["number"]},
        ),
        migrations.CreateModel(
            name="Source",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("url", models.URLField()),
                ("kind", models.CharField(choices=[("sub", "Sub"), ("dub", "Dub"), ("raw", "Raw")], default="sub", max_length=10)),
                ("availability", models.CharField(choices=[("available", "Available"), ("unavailable", "Unavailable"), ("geo_blocked", "Geo blocked"), ("expired", "Expired"), ("provider_error", "Provider error")], default="available", max_length=20)),
                ("availability_reason", models.CharField(blank=True, max_length=240)),
                ("episode", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sources", to="catalog.episode")),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.AddConstraint(model_name="episode", constraint=models.UniqueConstraint(fields=("title", "number"), name="unique_title_episode_number")),
        migrations.AddConstraint(model_name="source", constraint=models.UniqueConstraint(fields=("episode", "name", "kind"), name="unique_episode_source")),
    ]
