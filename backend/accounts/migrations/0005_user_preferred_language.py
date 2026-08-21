from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_telegramloginchallenge")]
    operations = [
        migrations.AddField(
            model_name="user",
            name="preferred_language",
            field=models.CharField(choices=[("ru", "Русский"), ("en", "English")], default="ru", max_length=8, verbose_name="Язык интерфейса"),
        ),
    ]
