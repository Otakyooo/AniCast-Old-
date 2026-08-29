from django.db import migrations, models


ROLE_LABELS = {
    "director": ("Режиссёр", "Director"),
    "producer": ("Продюсер", "Producer"),
    "writer": ("Сценарист", "Writer"),
    "composer": ("Композитор", "Composer"),
    "designer": ("Дизайнер", "Designer"),
}


def fill_labels(apps, schema_editor):
    TitleCredit = apps.get_model("catalog", "TitleCredit")
    for role, (ru, en) in ROLE_LABELS.items():
        TitleCredit.objects.filter(role=role).update(role_ru=ru, role_en=en)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0015_creator_image_url")]

    operations = [
        migrations.AlterField(
            model_name="titlecredit",
            name="role",
            field=models.CharField(max_length=80),
        ),
        migrations.AddField(
            model_name="titlecredit",
            name="role_en",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="titlecredit",
            name="role_ru",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RunPython(fill_labels, migrations.RunPython.noop),
    ]
