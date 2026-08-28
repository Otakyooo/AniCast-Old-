from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0014_source_playback_count")]

    operations = [
        migrations.AddField(
            model_name="creator",
            name="image_url",
            field=models.URLField(blank=True),
        ),
    ]
