from django.db import migrations, models
import django.db.models.deletion


LANGUAGES = [("ru", "Русский"), ("en", "English"), ("uk", "Українська"), ("be", "Беларуская"), ("kk", "Қазақша"), ("de", "Deutsch"), ("fr", "Français"), ("es", "Español"), ("it", "Italiano"), ("ja", "日本語"), ("ko", "한국어"), ("zh", "中文")]


def backfill_english(apps, schema_editor):
    Genre = apps.get_model("catalog", "Genre")
    GenreTranslation = apps.get_model("catalog", "GenreTranslation")
    Franchise = apps.get_model("catalog", "Franchise")
    FranchiseTranslation = apps.get_model("catalog", "FranchiseTranslation")
    Title = apps.get_model("catalog", "Title")
    TitleTranslation = apps.get_model("catalog", "TitleTranslation")
    Episode = apps.get_model("catalog", "Episode")
    EpisodeTranslation = apps.get_model("catalog", "EpisodeTranslation")
    russian_genres = {
        "Action": "Экшен", "Adventure": "Приключения", "Comedy": "Комедия", "Drama": "Драма",
        "Fantasy": "Фэнтези", "Romance": "Романтика", "Science Fiction": "Научная фантастика",
        "Sci-Fi": "Научная фантастика", "Mystery": "Мистика", "Horror": "Ужасы",
        "Sports": "Спорт", "Slice of Life": "Повседневность", "Thriller": "Триллер",
    }
    for item in Genre.objects.all():
        GenreTranslation.objects.get_or_create(genre=item, language="en", defaults={"name": item.name})
        if item.name in russian_genres:
            GenreTranslation.objects.get_or_create(genre=item, language="ru", defaults={"name": russian_genres[item.name]})
    for item in Franchise.objects.all():
        FranchiseTranslation.objects.get_or_create(franchise=item, language="en", defaults={"name": item.name, "description": item.description})
        if item.slug == "demo-franchise":
            FranchiseTranslation.objects.get_or_create(franchise=item, language="ru", defaults={"name": "Демо-франшиза", "description": "Тестовая франшиза каталога."})
    for item in Title.objects.all():
        TitleTranslation.objects.get_or_create(title=item, language="en", defaults={"name": item.name, "synopsis": item.synopsis})
        if item.slug == "demo-title":
            TitleTranslation.objects.get_or_create(title=item, language="ru", defaults={"name": "Демо-тайтл", "synopsis": "Детерминированный пример тайтла для разработки."})
    for item in Episode.objects.all():
        EpisodeTranslation.objects.get_or_create(episode=item, language="en", defaults={"name": item.name, "synopsis": item.synopsis})
        if item.title.slug == "demo-title" and item.number == 1:
            EpisodeTranslation.objects.get_or_create(episode=item, language="ru", defaults={"name": "Первый эпизод", "synopsis": "История начинается."})


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_source_health")]
    operations = [
        migrations.CreateModel(name="GenreTranslation", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("language", models.CharField(choices=LANGUAGES, max_length=8)), ("name", models.CharField(max_length=80)), ("genre", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="catalog.genre"))], options={"ordering": ["language"], "constraints": [models.UniqueConstraint(fields=("genre", "language"), name="unique_genre_language")]}),
        migrations.CreateModel(name="FranchiseTranslation", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("language", models.CharField(choices=LANGUAGES, max_length=8)), ("name", models.CharField(max_length=200)), ("description", models.TextField(blank=True)), ("franchise", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="catalog.franchise"))], options={"ordering": ["language"], "constraints": [models.UniqueConstraint(fields=("franchise", "language"), name="unique_franchise_language")]}),
        migrations.CreateModel(name="TitleTranslation", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("language", models.CharField(choices=LANGUAGES, max_length=8)), ("name", models.CharField(max_length=240)), ("synopsis", models.TextField(blank=True)), ("title", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="catalog.title"))], options={"ordering": ["language"], "constraints": [models.UniqueConstraint(fields=("title", "language"), name="unique_title_language")]}),
        migrations.CreateModel(name="EpisodeTranslation", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("language", models.CharField(choices=LANGUAGES, max_length=8)), ("name", models.CharField(blank=True, max_length=240)), ("synopsis", models.TextField(blank=True)), ("episode", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="catalog.episode"))], options={"ordering": ["language"], "constraints": [models.UniqueConstraint(fields=("episode", "language"), name="unique_episode_language")]}),
        migrations.RunPython(backfill_english, migrations.RunPython.noop),
    ]
