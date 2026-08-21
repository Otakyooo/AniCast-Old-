from django.db import migrations, models
import django.db.models.deletion
import django.db.models.functions.text


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_alter_user_options_alter_user_groups")]
    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower("email"), name="unique_user_email_ci"),
        ),
        migrations.CreateModel(
            name="ExternalIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("telegram", "Telegram")], max_length=32)),
                ("subject", models.CharField(max_length=128)),
                ("username", models.CharField(blank=True, max_length=128)),
                ("display_name", models.CharField(blank=True, max_length=256)),
                ("avatar_url", models.URLField(blank=True, max_length=2048)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_authenticated_at", models.DateTimeField()),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="external_identities", to="accounts.user")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("provider", "subject"), name="unique_external_identity")]},
        ),
    ]
