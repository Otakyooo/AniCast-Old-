from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [
        migrations.AlterModelOptions(
            name="franchise",
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.RenameIndex(
            model_name="title",
            new_name="catalog_tit_status_7618c9_idx",
            old_name="catalog_ti_status_4d77e1_idx",
        ),
        migrations.RenameIndex(
            model_name="title",
            new_name="catalog_tit_title_t_491ef3_idx",
            old_name="catalog_ti_title_t_ef7d7b_idx",
        ),
    ]
