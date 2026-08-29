import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.urls import reverse

from accounts.models import User
from catalog.admin import ProviderAdminForm, SourceAdminForm
from catalog.models import Character, Creator, Episode, Genre, Provider, Source, SourceReport, Title, TitleCharacter


@pytest.fixture
def staff_client(client, db):
    user = User.objects.create_superuser(email="admin@example.com", password="A-strong-admin-passphrase-2042")
    client.force_login(user)
    return client


POSTER_FALLBACK_URL = "https://cdn.test/api/v1/media/posters/22-l-0123456789abcdef.png"


@pytest.mark.django_db
def test_staff_index_renders_editor_dashboard(staff_client):
    reporter = User.objects.create_user(email="dash-reporter@example.com", password="A-strong-passphrase-2042")
    title = Title.objects.create(
        name="Dash", slug="21-dash",
        poster_url="https://cdn.test/api/v1/media/posters/21-s-ab12cd34.png",
    )
    episode = Episode.objects.create(title=title, number=1)
    broken = Source.objects.create(
        episode=episode, name="Broken Provider", url="https://example.invalid/broken",
        availability="provider_error",
    )
    SourceReport.objects.create(source=broken, reporter=reporter, reason="unavailable")
    hero = Character.objects.create(name="No Art Hero", slug="no-art-hero")
    TitleCharacter.objects.create(title=title, character=hero, role="protagonist")
    Creator.objects.create(name="No Art Author", slug="no-art-author")

    response = staff_client.get("/staff/")
    assert response.status_code == 200
    dashboard = {item["label"]: item for item in response.context["dashboard"]}
    assert dashboard["Новые жалобы"]["value"] == 1
    assert "status__exact=new" in dashboard["Новые жалобы"]["url"]
    assert dashboard["Источники с ошибкой провайдера"]["value"] == 1
    assert dashboard["Эпизоды без даты выхода"]["value"] >= 1
    assert dashboard["Постеры ниже максимума"]["value"] >= 1
    assert dashboard["Персонажи без аватара"]["value"] == 1
    assert dashboard["Главные герои без аватара"]["value"] == 1
    assert dashboard["Авторы без фото"]["value"] == 1

    html = response.content.decode()
    assert 'aria-label="Сводка редактора"' in html
    # A danger tone marks actionable counters; links lead into prefiltered lists.
    assert "staff-dash-card--danger" in html
    assert "/staff/catalog/sourcereport/?status__exact=new" in html


@pytest.mark.django_db
def test_staff_index_requires_staff_like_stock_admin(client):
    response = client.get("/staff/")
    assert response.status_code == 302
    assert response.url.startswith("/staff/login/")


@pytest.mark.django_db
def test_title_changelist_shows_poster_preview_and_tier(staff_client):
    Title.objects.create(name="Tiered", slug="22-tiered", poster_url=POSTER_FALLBACK_URL)
    Title.objects.create(name="Bare", slug="23-bare", poster_url="")
    response = staff_client.get(reverse("admin:catalog_title_changelist"))
    assert response.status_code == 200
    html = response.content.decode()
    assert POSTER_FALLBACK_URL in html
    assert ">l</span>" in html
    assert ">нет</span>" in html


@pytest.mark.django_db
def test_source_changelist_marks_availability_with_pill(staff_client):
    title = Title.objects.create(name="Pill", slug="24-pill")
    episode = Episode.objects.create(title=title, number=1)
    Source.objects.create(episode=episode, name="Geo", url="https://example.invalid/geo", availability="geo_blocked")
    response = staff_client.get(reverse("admin:catalog_source_changelist"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Geo blocked" in html
    assert "#b45309" in html


@pytest.mark.django_db
def test_admin_requires_staff(client):
    response = client.get("/staff/")
    assert response.status_code == 302
    assert response.url.startswith("/staff/login/")
    login_redirect = client.get("/staff/login/?next=/staff/")
    assert login_redirect.status_code == 302
    assert login_redirect.url == "/login?next=%2Fstaff%2F"

    user = User.objects.create_user(email="viewer@example.com", password="A-strong-passphrase-2042")
    client.force_login(user)
    assert client.get("/staff/").status_code == 302

    static_response = client.get("/static/admin/css/base.css")
    assert static_response.status_code == 200
    assert static_response["Content-Type"].startswith("text/css")


@pytest.mark.django_db
def test_staff_can_open_admin_and_changes_are_audited(staff_client):
    assert staff_client.get("/staff/").status_code == 200
    assert staff_client.get("/staff/login/").url == "/staff/"
    response = staff_client.post(
        reverse("admin:catalog_genre_add"),
        {
            "name": "Science Fiction", "slug": "science-fiction", "_save": "Сохранить",
            "translations-TOTAL_FORMS": "1", "translations-INITIAL_FORMS": "0",
            "translations-MIN_NUM_FORMS": "0", "translations-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 302
    genre = Genre.objects.get(slug="science-fiction")
    log_entry = LogEntry.objects.get(object_id=str(genre.pk))
    assert log_entry.action_flag == ADDITION
    assert log_entry.user.email == "admin@example.com"


@pytest.mark.django_db
def test_staff_report_action_updates_handler_and_audit_log(staff_client):
    reporter = User.objects.create_user(email="reporter@example.com", password="A-strong-passphrase-2042")
    title = Title.objects.create(name="Report Test", slug="report-test")
    episode = Episode.objects.create(title=title, number=1)
    source = Source.objects.create(episode=episode, name="Provider", url="https://example.invalid/report")
    report = SourceReport.objects.create(source=source, reporter=reporter, reason="unavailable")
    response = staff_client.post(
        reverse("admin:catalog_sourcereport_changelist"),
        {"action": "mark_resolved", "_selected_action": [str(report.pk)], "index": "0"},
    )
    assert response.status_code == 302
    report.refresh_from_db()
    assert report.status == SourceReport.Status.RESOLVED
    assert report.handled_by.email == "admin@example.com"
    assert report.handled_at is not None
    assert LogEntry.objects.filter(object_id=str(report.pk), change_message__contains="Решена").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("adapter", "config", "hosts"),
    [
        ("unknown", "{}", '["watch.example.com"]'),
        ("external_link", '{"token": "secret"}', '["watch.example.com"]'),
        ("external_link", "{}", '["https://watch.example.com/path"]'),
        ("external_link", "{}", '["127.0.0.1"]'),
    ],
)
def test_provider_admin_form_rejects_unsafe_playback_configuration(adapter, config, hosts):
    form = ProviderAdminForm(data={
        "name": "Unsafe Provider",
        "slug": "unsafe-provider",
        "website_url": "",
        "allowed_hosts": hosts,
        "playback_adapter": adapter,
        "playback_config": config,
        "is_enabled": True,
    })
    assert form.is_valid() is False
    assert "__all__" in form.errors


@pytest.mark.django_db
def test_source_admin_form_rejects_url_outside_provider_allowlist():
    provider = Provider.objects.create(
        name="Admin Provider",
        slug="admin-provider",
        allowed_hosts=["watch.example.com"],
        playback_adapter="external_link",
    )
    title = Title.objects.create(name="Admin Playback", slug="admin-playback")
    episode = Episode.objects.create(title=title, number=1)
    form = SourceAdminForm(data={
        "episode": episode.pk,
        "provider": provider.pk,
        "name": "Unsafe Source",
        "url": "https://evil.example.com/episode/1",
        "kind": "sub",
        "availability": "available",
        "availability_reason": "",
        "consecutive_failures": 0,
    })
    assert form.is_valid() is False
    assert "__all__" in form.errors
