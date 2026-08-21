from django.db import migrations, models


LANGUAGES = [("ru", "Русский"), ("en", "English"), ("uk", "Українська"), ("be", "Беларуская"), ("kk", "Қазақша"), ("de", "Deutsch"), ("fr", "Français"), ("es", "Español"), ("it", "Italiano"), ("ja", "日本語"), ("ko", "한국어"), ("zh", "中文")]


class Migration(migrations.Migration):
    dependencies = [("catalog", "0006_content_translations")]
    operations = [
        migrations.AlterModelOptions(name="episode", options={"ordering": ["number"], "verbose_name": "Эпизод", "verbose_name_plural": "Эпизоды"}),
        migrations.AlterModelOptions(name="episodetranslation", options={"ordering": ["language"], "verbose_name": "Перевод эпизода", "verbose_name_plural": "Переводы эпизода"}),
        migrations.AlterModelOptions(name="franchise", options={"ordering": ["sort_order", "name"], "verbose_name": "Франшиза", "verbose_name_plural": "Франшизы"}),
        migrations.AlterModelOptions(name="franchisetranslation", options={"ordering": ["language"], "verbose_name": "Перевод франшизы", "verbose_name_plural": "Переводы франшизы"}),
        migrations.AlterModelOptions(name="genre", options={"ordering": ["name"], "verbose_name": "Жанр", "verbose_name_plural": "Жанры"}),
        migrations.AlterModelOptions(name="genretranslation", options={"ordering": ["language"], "verbose_name": "Перевод жанра", "verbose_name_plural": "Переводы жанра"}),
        migrations.AlterModelOptions(name="title", options={"ordering": ["name"], "verbose_name": "Тайтл", "verbose_name_plural": "Тайтлы"}),
        migrations.AlterModelOptions(name="titletranslation", options={"ordering": ["language"], "verbose_name": "Перевод тайтла", "verbose_name_plural": "Переводы тайтла"}),
        migrations.AlterField(model_name="episodetranslation", name="language", field=models.CharField("Язык", choices=LANGUAGES, max_length=8)),
        migrations.AlterField(model_name="episodetranslation", name="name", field=models.CharField("Название", blank=True, max_length=240)),
        migrations.AlterField(model_name="episodetranslation", name="synopsis", field=models.TextField("Описание", blank=True)),
        migrations.AlterField(model_name="franchisetranslation", name="description", field=models.TextField("Описание", blank=True)),
        migrations.AlterField(model_name="franchisetranslation", name="language", field=models.CharField("Язык", choices=LANGUAGES, max_length=8)),
        migrations.AlterField(model_name="franchisetranslation", name="name", field=models.CharField("Название", max_length=200)),
        migrations.AlterField(model_name="genretranslation", name="language", field=models.CharField("Язык", choices=LANGUAGES, max_length=8)),
        migrations.AlterField(model_name="genretranslation", name="name", field=models.CharField("Название", max_length=80)),
        migrations.AlterField(model_name="titletranslation", name="language", field=models.CharField("Язык", choices=LANGUAGES, max_length=8)),
        migrations.AlterField(model_name="titletranslation", name="name", field=models.CharField("Название", max_length=240)),
        migrations.AlterField(model_name="titletranslation", name="synopsis", field=models.TextField("Описание", blank=True)),
    ]
