"""CI-only browser fixture: real Django APIs, disposable SQLite, no workers/mail.

Settings live in this process, never in production configuration. Only the
external video frame is stubbed by Playwright; sessions/CSRF/history/resolvers
run through the application's real views. Throttle capacity is tested elsewhere.
"""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

seed_check = sys.argv[1:] == ["--seed-check"]
if not seed_check and (os.environ.get("CI") != "true" or os.environ.get("ANICAST_E2E") != "1"):
    raise SystemExit("This fixture is restricted to the isolated CI browser job")

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DATABASE_URL"] = "sqlite://e2e"
os.environ["DJANGO_SECRET_KEY"] = "ci-browser-fixture-not-a-production-secret"

import config.settings as settings

with TemporaryDirectory(prefix="anicast-browser-") as directory:
    settings.DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(Path(directory) / "test.sqlite3"),
        # SQLite has no SELECT FOR UPDATE. Serialize its write transactions
        # before reads, avoiding deferred-lock upgrades during browser events.
        # Production PostgreSQL row-lock behavior remains a separate check.
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
    }}
    settings.DEBUG = True
    settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
    settings.CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:3100"]
    settings.SECURE_SSL_REDIRECT = False
    settings.CSRF_COOKIE_SECURE = False
    settings.SESSION_COOKIE_SECURE = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.CELERY_BROKER_URL = "memory://"
    settings.CELERY_RESULT_BACKEND = "cache+memory://"
    settings.TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_NOTIFY_BOT_TOKEN = ""
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        key: "10000/min" for key in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    }

    import django
    django.setup()
    from django.core.management import call_command
    from django.core.servers.basehttp import run
    from django.core.wsgi import get_wsgi_application
    from django.utils import timezone
    from accounts.models import User
    from catalog.models import Episode, Provider, Source, Title
    from library.models import EpisodeProgress

    call_command("migrate", verbosity=0, interactive=False)
    title = Title.objects.create(name="Browser fixture", slug="browser-fixture", title_type="anime", status="finished")
    provider = Provider.objects.create(
        name="Fixture", slug="fixture", is_enabled=True,
        allowed_hosts=["kodikplayer.com"], playback_adapter="iframe_embed",
        rights_reference="Synthetic CI fixture", rights_verified_at=timezone.now(),
    )
    episodes = []
    for number in (1, 2):
        episode = Episode.objects.create(title=title, number=number, name=f"Fixture episode {number}")
        episodes.append(episode)
        for voice in ("Alpha", "Beta"):
            Source.objects.create(
                episode=episode, provider=provider, name=voice, kind="dub",
                url=f"https://kodikplayer.com/seria/fixture-{number}-{voice}/test/720p",
            )
    # Login helpers address users as f"{project.name}-{scenario}": seed every
    # Playwright project name, including the opt-in Firefox/WebKit desktops
    # from playwright.config.ts (E2E_BROWSERS=all). Keep the lists in sync.
    for viewport in ("desktop", "laptop", "tablet", "mobile", "firefox-desktop", "webkit-desktop"):
        for scenario in ("auth", "player", "switch"):
            user = User.objects.create_user(
                email=f"{viewport}-{scenario}@example.invalid",
                display_name=f"Fixture {viewport} {scenario}",
                password="Browser-fixture-passphrase-2042",
                email_verified_at=timezone.now(),
            )
            if scenario == "player":
                EpisodeProgress.objects.create(user=user, episode=episodes[0], watched_seconds=120, duration_seconds=1200, last_opened_at=timezone.now())
    print("Disposable browser API ready", flush=True)
    if seed_check:
        from django.test import Client
        client = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1:3100")
        assert client.get("/api/v1/titles/browser-fixture/").status_code == 200
        assert client.get("/api/v1/sources/1/playback/").status_code == 200
        csrf = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
        assert client.post("/api/v1/auth/login/", {
            "email": "desktop-player@example.invalid", "password": "Browser-fixture-passphrase-2042",
        }, content_type="application/json", HTTP_X_CSRFTOKEN=csrf,
            HTTP_ORIGIN="http://127.0.0.1:3100").status_code == 200
        assert client.get("/api/v1/episodes/browser-fixture/1/progress/").json()["watched_seconds"] == 120
        from django.db import connections
        connections.close_all()
        print("Fixture seed and real catalogue/playback views verified without a listener")
    else:
        from urllib.parse import parse_qs

        application = get_wsgi_application()

        def fault_fixture(environ, start_response):
            # SSR failure evidence needs a server-side fault, not a browser
            # fetch mock. This wrapper exists only in the disposable CI process.
            query = parse_qs(environ.get("QUERY_STRING", ""))
            path = environ.get("PATH_INFO", "")
            unavailable = (
                path == "/api/v1/titles/" and query.get("q") == ["e2e-unavailable"]
            ) or (
                path == "/api/v1/schedule/" and query.get("from", [""])[0].startswith("2111-")
            )
            if unavailable:
                start_response("503 Service Unavailable", [("Content-Type", "application/json")])
                return [b'{"detail":"Synthetic outage"}']
            return application(environ, start_response)

        run("127.0.0.1", 8000, fault_fixture, threading=True)
