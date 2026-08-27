from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0013_creator_titlecredit_provider_rights_and_duration")]

    operations = [
        migrations.AddField(
            model_name="source",
            name="playback_count",
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
