"""Synthetic write-path checks ONLY in restore-isolated.py's disposable DB.

Outbound network is disabled by Docker. Email stays in memory, Telegram is a
capture sink. All synthetic changes roll back; never run with production env.
"""
import json
import os
import re
import secrets
import sys
import traceback
from unittest.mock import patch

# Show the failing code location, never an exception value containing user data.
sys.excepthook = lambda kind, value, tb: print(f"drill_flow_error={kind.__name__} line={traceback.extract_tb(tb)[-1].lineno}", file=sys.stderr)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection, transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import AccountEmail
from accounts.tasks import dispatch_account_emails
from catalog.playback import authorized_playback_source
from catalog.models import Source
from push.models import EventNotification, TelegramNotificationChannel
from push.tasks import dispatch_event_notifications

assert os.environ.get("DRILL_WRITE_FLOWS") == "1"
assert connection.settings_dict["HOST"].startswith("anicast-restore-")
assert connection.settings_dict["NAME"] == "recovery"
caches = {alias: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": alias} for alias in ("default", "ephemeral")}
with override_settings(CACHES=caches, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", TELEGRAM_NOTIFY_BOT_TOKEN="isolated-sink"), transaction.atomic():
    # Do not replay the restored users' pending messages even into test sinks.
    AccountEmail.objects.all().update(status=AccountEmail.Status.EXPIRED)
    EventNotification.objects.all().update(status=EventNotification.Status.SENT)
    password = secrets.token_urlsafe(32)
    user = get_user_model().objects.create_user(display_name="Recovery drill", email="drill-" + secrets.token_hex(6) + "@example.invalid", password=password, email_verified_at=timezone.now())
    client = APIClient(enforce_csrf_checks=True)
    def post(path, data):
        csrf = client.get("/api/v1/auth/csrf/", secure=True).json()["csrfToken"]
        return client.post(path, data, format="json", secure=True, HTTP_X_CSRFTOKEN=csrf, HTTP_ORIGIN="https://testserver")
    assert post("/api/v1/auth/login/", {"email": user.email, "password": password}).status_code == 200, "session login failed"
    assert client.get("/api/v1/library/", secure=True).status_code == 200, "session-protected API failed"
    assert post("/api/v1/auth/logout/", {}).status_code == 204
    assert client.get("/api/v1/library/", secure=True).status_code in (401, 403)
    with patch("accounts.tasks.dispatch_account_emails.delay"):
        assert post("/api/v1/auth/password/reset/", {"email": user.email}).status_code == 202
    result = dispatch_account_emails()
    assert result["sent"] == 1 and len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    token = re.search(r"[?&]token=([A-Za-z0-9_-]+)", mail.outbox[0].body).group(1)
    replacement = secrets.token_urlsafe(32)
    assert post("/api/v1/auth/password/reset/confirm/", {"token": token, "password": replacement}).status_code == 200
    assert post("/api/v1/auth/password/reset/confirm/", {"token": token, "password": replacement}).status_code == 400, "reset token was reusable"
    user.refresh_from_db()
    assert user.check_password(replacement) and not user.check_password(password)
    TelegramNotificationChannel.objects.create(user=user, telegram_user_id=-999999999, chat_id=-999999999)
    event = EventNotification.objects.create(user=user, kind=EventNotification.Kind.REPORT_RESOLVED, context="isolated drill", url_path="/library")
    with patch("push.tasks.send_notification") as sink:
        dispatch_event_notifications()
        assert sink.call_count == 1 and sink.call_args.args[0] == -999999999
    event.refresh_from_db()
    assert event.status == EventNotification.Status.SENT
    source_id = next((pk for pk in Source.objects.filter(availability="available").values_list("pk", flat=True).iterator() if authorized_playback_source(pk)), None)
    assert source_id is not None, "restored catalogue has no authorized playback source"
    target = client.get(f"/api/v1/sources/{source_id}/playback/", secure=True)
    assert target.status_code == 200
    resolved = client.get(target.json()["url"], secure=True)
    assert resolved.status_code == 302 and resolved["Location"].startswith("https://")
    transaction.set_rollback(True)
print(json.dumps({"session_login": "passed", "password_reset_single_use": "passed", "email_sink": "passed", "notification_sink": "passed", "playback_issue_resolve": "passed", "external_delivery": "not attempted", "writes": "rolled back"}))
