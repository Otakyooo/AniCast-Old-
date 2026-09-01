from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0005_recommendationdismissal"),
    ]

    operations = [
        migrations.AddField(
            model_name="episodeprogress",
            name="duration_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="episodeprogress",
            name="watched_seconds",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
