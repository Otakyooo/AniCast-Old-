from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0004_provider_rightsgrant_source_provider"),
    ]
    operations = [
        migrations.CreateModel(
            name="TelegramNotificationChannel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("telegram_user_id", models.BigIntegerField(unique=True)), ("chat_id", models.BigIntegerField(unique=True)),
                ("username", models.CharField(blank=True, max_length=128)), ("is_active", models.BooleanField(default=True)),
                ("linked_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("disabled_at", models.DateTimeField(blank=True, null=True)), ("last_error", models.CharField(blank=True, max_length=500)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="telegram_notification_channel", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="TelegramNotificationChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=64, unique=True)), ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="telegram_notification_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [models.Index(fields=["expires_at", "consumed_at"], name="push_telegr_expires_2ede66_idx")]},
        ),
        migrations.CreateModel(
            name="TitleNotificationSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_subscriptions", to="catalog.title")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="title_notification_subscriptions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "-id"], "constraints": [models.UniqueConstraint(fields=("user", "title"), name="unique_user_title_notification")]},
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Ожидает"), ("sent", "Отправлено"), ("failed", "Ошибка")], default="pending", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)), ("error", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("sent_at", models.DateTimeField(blank=True, null=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("episode", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_deliveries", to="catalog.episode")),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="push.titlenotificationsubscription")),
            ],
            options={"ordering": ["-created_at", "-id"], "constraints": [models.UniqueConstraint(fields=("subscription", "episode"), name="unique_subscription_episode_delivery")]},
        ),
    ]
