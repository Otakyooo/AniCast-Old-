import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.urls import reverse

from accounts.models import User
from catalog.models import Episode, Genre, Source, SourceReport, Title


@pytest.fixture
def staff_client(client, db):
    user = User.objects.create_superuser(email="admin@example.com", password="A-strong-admin-passphrase-2042")
    client.force_login(user)
    return client


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
