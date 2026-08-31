from django.db import migrations, models
from django.db.models import F, Q


PRIVATE_ORIGIN = Q(image_url__startswith="https://shikimori.one/") | Q(
    image_url__startswith="https://shikimori.io/"
) | Q(image_url__startswith="https://cdn.myanimelist.net/")


def copy_private_origins(apps, schema_editor):
    for model_name in ("Character", "Creator"):
        model = apps.get_model("catalog", model_name)
        model.objects.filter(PRIVATE_ORIGIN).update(
            image_origin_url=F("image_url"),
        )


def clear_private_origins(apps, schema_editor):
    for model_name in ("Character", "Creator"):
        model = apps.get_model("catalog", model_name)
        model.objects.update(image_origin_url="")


class Migration(migrations.Migration):
    dependencies = [("catalog", "0016_titlecredit_exact_roles")]

    operations = [
        migrations.AddField(
            model_name="character",
            name="image_origin_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="creator",
            name="image_origin_url",
            field=models.URLField(blank=True),
        ),
        # Expand/contract: keep image_url intact during the rollback window.
        # New serializers already fail closed and the mirror command replaces
        # it with local media; an older image can still read the legacy field.
        migrations.RunPython(copy_private_origins, clear_private_origins),
    ]
