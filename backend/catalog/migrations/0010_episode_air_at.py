from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_provider_playback_adapter_provider_playback_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="episode",
            name="air_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Точное время выхода"),
        ),
        migrations.AddIndex(
            model_name="episode",
            index=models.Index(fields=["air_date"], name="catalog_epi_air_dat_9939cc_idx"),
        ),
        migrations.AddIndex(
            model_name="episode",
            index=models.Index(fields=["air_at"], name="catalog_epi_air_at_83db9c_idx"),
        ),
    ]
