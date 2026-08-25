from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("catalog", "0011_title_poster_origin_url")]

    operations = [
        migrations.RemoveConstraint(
            model_name="source",
            name="unique_episode_source",
        ),
        migrations.AddField(
            model_name="source",
            name="external_id",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddConstraint(
            model_name="source",
            constraint=models.UniqueConstraint(
                condition=Q(external_id=""),
                fields=("episode", "name", "kind"),
                name="unique_manual_episode_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="source",
            constraint=models.UniqueConstraint(
                condition=~Q(external_id=""),
                fields=("provider", "episode", "external_id"),
                name="unique_provider_episode_external_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="source",
            constraint=models.CheckConstraint(
                condition=Q(external_id="") | Q(provider__isnull=False),
                name="external_source_requires_provider",
            ),
        ),
    ]
