from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_externalidentity_alter_user_email")]
    operations = [
        migrations.CreateModel(
            name="TelegramLoginChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("session_hash", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("consumed", "Consumed"), ("expired", "Expired")], default="pending", max_length=16)),
                ("expires_at", models.DateTimeField()),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="telegram_login_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [models.Index(fields=["status", "expires_at"], name="accounts_te_status_06a227_idx")]},
        ),
    ]
