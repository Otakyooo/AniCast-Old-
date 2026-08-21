import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.urls import reverse

from accounts.models import User
from catalog.models import Genre


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

    user = User.objects.create_user(email="viewer@example.com", password="A-strong-passphrase-2042")
    client.force_login(user)
    assert client.get("/staff/").status_code == 302

    static_response = client.get("/static/admin/css/base.css")
    assert static_response.status_code == 200
    assert static_response["Content-Type"].startswith("text/css")


@pytest.mark.django_db
def test_staff_can_open_admin_and_changes_are_audited(staff_client):
    assert staff_client.get("/staff/").status_code == 200
    response = staff_client.post(
        reverse("admin:catalog_genre_add"),
        {"name": "Science Fiction", "slug": "science-fiction", "_save": "Сохранить"},
    )
    assert response.status_code == 302
    genre = Genre.objects.get(slug="science-fiction")
    log_entry = LogEntry.objects.get(object_id=str(genre.pk))
    assert log_entry.action_flag == ADDITION
    assert log_entry.user.email == "admin@example.com"
