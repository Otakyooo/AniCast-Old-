import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "rest_framework",
    "common.apps.CommonConfig",
    "catalog",
    "accounts",
    "library",
    "push",
    "community",
]
MIDDLEWARE = [
    "common.middleware.ObservabilityMiddleware",
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES: dict[str, Any] = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ.get("POSTGRES_DB", "anicast"), "USER": os.environ.get("POSTGRES_USER", "anicast"), "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "anicast-dev"), "HOST": os.environ.get("POSTGRES_HOST", "postgres"), "PORT": os.environ.get("POSTGRES_PORT", "5432"), "CONN_MAX_AGE": int(os.environ.get("DJANGO_CONN_MAX_AGE", "60")), "CONN_HEALTH_CHECKS": True}}
USE_SQLITE = os.environ.get("DJANGO_DATABASE_URL", "").startswith("sqlite")
if USE_SQLITE:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
# The placeholder key signs sessions, the visit cookie and playback tokens, so
# it must never reach a real deployment. DEBUG is deliberately not part of the
# condition: a production stack booted with DJANGO_DEBUG=1 by accident would
# otherwise run on a publicly known key.
if SECRET_KEY == "dev-only-change-me" and not USE_SQLITE and not os.environ.get("DJANGO_ALLOW_DEV_SECRET"):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set outside local development")
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = os.environ.get("TZ", "UTC")
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
ROOT_URLCONF = "config.urls"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
# The frontend never reads this cookie: it takes the token from the body of
# /api/v1/auth/csrf/ (frontend/lib/auth.ts:getCsrfToken). Keeping it readable by
# script bought nothing and handed any injected script the token for free.
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
# Rolling expiry rather than absolute: an active viewer stays signed in, an idle
# one is logged out after 30 days. The cost is one session UPDATE per request,
# which is measurable only well above current traffic. Turning it off would log
# everyone out 30 days after login regardless of use, so it stays deliberate.
SESSION_SAVE_EVERY_REQUEST = True
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x]
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    # Bound list responses by default. Every current list view sets its own
    # pagination class, so this changes no existing endpoint; it exists so the
    # next ListAPIView cannot ship unbounded by omission. Opting out stays
    # explicit (`pagination_class = None`) for the few genuinely small lists.
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Anonymous and authenticated traffic need separate ceilings: DRF's
    # AnonRateThrottle silently skips authenticated requests, which would leave
    # every logged-in account unthrottled on the expensive personal endpoints.
    "DEFAULT_THROTTLE_CLASSES": [
        "common.throttling.AniCastAnonRateThrottle",
        "common.throttling.AniCastUserRateThrottle",
    ],
    # Exactly one trusted proxy (Caddy) sits in front, and it appends the peer
    # address to any inbound X-Forwarded-For. Without this setting DRF keys
    # throttles on the whole header, so a client-supplied prefix would mint a
    # fresh bucket per request and defeat every rate limit, including the login
    # one. With 1, only the address Caddy appended is trusted.
    "NUM_PROXIES": int(os.environ.get("DJANGO_NUM_PROXIES", "1")),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "240/min",
        "ssr": "600/min",
        "auth": "10/min",
        # Registration is an account-enumeration oracle by construction: unlike
        # login it must tell a returning user their address is taken. An hourly
        # bucket is invisible to someone registering once and makes probing
        # impractical. See RegisterRateThrottle.
        "register": "20/hour",
        "playback": "30/min",
        "telegram_challenge": "20/min",
        # Account mail is the only channel that can reach a stranger's inbox on
        # request, so it is bounded twice: this per-address bucket, plus a
        # per-target bucket inside the view (see accounts.views.MailRateThrottle).
        # Hourly, because a person who lost their password tries a handful of
        # times, while a script would use it to flood a victim's mailbox.
        "account_mail": "10/hour",
        "visit": "600/hour",
    },
}
CACHES: dict[str, Any]
if USE_SQLITE:
    CACHES = {
        alias: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": alias}
        for alias in ("default", "ephemeral")
    }
else:
    from redis.backoff import NoBackoff
    from redis.retry import Retry

    # The default cache is coordination state: throttles, locks and cursors
    # must not be evicted by optional telemetry or future response caching.
    # Fallback keeps older deployments compatible until their env is migrated.
    _cache_url = os.environ.get("CACHE_URL", "redis://redis:6379/2")
    CACHES = {
        alias: {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": url,
            "OPTIONS": {
                "socket_connect_timeout": 0.3, "socket_timeout": 0.3,
                "retry": Retry(NoBackoff(), 0),
            },
        }
        for alias, url in {
            "default": os.environ.get("CONTROL_CACHE_URL", _cache_url),
            "ephemeral": _cache_url,
        }.items()
    }
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_NOTIFY_BOT_TOKEN = os.environ.get("TELEGRAM_NOTIFY_BOT_TOKEN", "")
TELEGRAM_NOTIFY_BOT_USERNAME = os.environ.get("TELEGRAM_NOTIFY_BOT_USERNAME", "")
TELEGRAM_NOTIFY_WEBHOOK_SECRET = os.environ.get("TELEGRAM_NOTIFY_WEBHOOK_SECRET", "")
# api.telegram.org is unreachable from MainServer, so production points this at
# the relay Caddy exposes inside the tunnel. The default is the direct upstream:
# local development and any host with working egress need no configuration.
TELEGRAM_API_BASE_URL = os.environ.get("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
# Outbound mail. Unlike api.telegram.org, SMTP egress from MainServer works:
# verified on 2026-09-04 from both the host and the backend container, where
# 587/465 connect and STARTTLS completes against Gmail, Yandex, Resend, Postmark
# and SES. The network block that forced the Telegram relay is specific to
# Telegram's address range, so account mail needs no relay — only credentials.
#
# EMAIL_HOST unset is a supported state, not a broken one: every endpoint that
# would send mail answers 503 with a plain reason instead of failing mid-flow.
# See accounts/mail.py:mail_is_configured and docs/OPERATIONS.md.
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
# Implicit TLS (465) and STARTTLS (587) are mutually exclusive, and Django raises
# on both being set — at send time, inside the task, where it would look like a
# transient delivery failure. Deriving one from the other makes the port choice
# the only decision an operator has to get right.
EMAIL_USE_TLS = not EMAIL_USE_SSL and os.environ.get("EMAIL_USE_TLS", "1") == "1"
# Bounded well below the Celery soft time limit: a hung SMTP server must fail
# the one delivery, not the whole batch.
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "AniCast <noreply@anicast.online>")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
# Lifetime of both signed account links (reset and verification). Django's own
# default for its unused built-in flow is three days, which is a long window for
# a link that grants a password change. A day still absorbs slow mail without
# leaving the link alive for long.
ACCOUNT_LINK_TTL_SECONDS = int(os.environ.get("ACCOUNT_LINK_TTL_SECONDS", str(60 * 60 * 24)))
KODIK_API_TOKEN = os.environ.get("KODIK_API_TOKEN", "")
INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "")
PLAYBACK_URL_TTL_SECONDS = int(os.environ.get("PLAYBACK_URL_TTL_SECONDS", "60"))
POSTERS_MEDIA_ROOT = Path(os.environ.get("POSTERS_MEDIA_ROOT", str(BASE_DIR / "media" / "posters")))
POSTERS_PUBLIC_BASE = os.environ.get("POSTERS_PUBLIC_BASE", "https://anicast.online").rstrip("/")
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TASK_ROUTES = {
    "accounts.tasks.dispatch_account_emails": {"queue": "notifications"},
    "push.tasks.dispatch_episode_notifications": {"queue": "notifications"},
    "push.tasks.dispatch_event_notifications": {"queue": "notifications"},
    "push.tasks.send_schedule_digest": {"queue": "notifications"},
    "catalog.tasks.check_provider_sources": {"queue": "providers"},
    "catalog.tasks.refresh_title_posters": {"queue": "posters"},
    "catalog.tasks.sync_kodik_library": {"queue": "providers"},
    "catalog.tasks.sync_episode_metadata_library": {"queue": "providers"},
    "catalog.tasks.sync_character_library": {"queue": "providers"},
    "common.tasks.probe_site_availability": {"queue": "default"},
}
CELERY_TASK_SOFT_TIME_LIMIT = 540
CELERY_TASK_TIME_LIMIT = 570
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# Enqueueing is on the user's request path: `enqueue_account_email` and
# `enqueue_event_notification` write the ledger row first and then dispatch
# best-effort, so a broker outage is meant to cost nothing. Kombu's defaults
# retry 20 times at one-second intervals, which turned "Redis is down" into a
# 20-second wait on registration and password reset before the same fallback ran.
# Two quick attempts still ride out a reconnect; anything longer belongs to beat.
_CELERY_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.2, "interval_max": 0.5}
CELERY_TASK_PUBLISH_RETRY_POLICY = _CELERY_RETRY_POLICY
CELERY_BROKER_TRANSPORT_OPTIONS = {"retry_policy": _CELERY_RETRY_POLICY}
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {"retry_policy": _CELERY_RETRY_POLICY}
# The worker itself must keep retrying: it has no request waiting on it, and
# giving up would leave the queue unconsumed after a Redis restart.
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "dispatch-account-emails": {
        "task": "accounts.tasks.dispatch_account_emails",
        # The ledger row is written before the task is enqueued, so this run is
        # what guarantees delivery when the broker was unavailable at request
        # time. Five minutes is short enough that a reset link still arrives
        # usefully within its lifetime.
        "schedule": 300.0,
    },
    "dispatch-episode-notifications": {
        "task": "push.tasks.dispatch_episode_notifications",
        "schedule": 900.0,
    },
    "dispatch-event-notifications": {
        "task": "push.tasks.dispatch_event_notifications",
        "schedule": 900.0,
    },
    "send-schedule-digest": {
        "task": "push.tasks.send_schedule_digest",
        # Runs continuously; the per-channel last_digest_date guard makes it
        # deliver at most once a day and retry failures within 15 minutes.
        "schedule": 900.0,
    },
    "check-provider-sources": {
        "task": "catalog.tasks.check_provider_sources",
        "schedule": 600.0,
    },
    "refresh-title-posters": {
        "task": "catalog.tasks.refresh_title_posters",
        "schedule": 21600.0,
        "options": {"soft_time_limit": 1500, "time_limit": 1800},
    },
    "sync-kodik-library": {
        "task": "catalog.tasks.sync_kodik_library",
        "schedule": 3600.0,
    },
    "sync-episode-metadata-library": {
        "task": "catalog.tasks.sync_episode_metadata_library",
        "schedule": 900.0,
    },
    "sync-character-library": {
        "task": "catalog.tasks.sync_character_library",
        "schedule": 3600.0,
    },
    "probe-site-availability": {
        "task": "common.tasks.probe_site_availability",
        # Minute resolution like public status pages: three bounded HTTP GETs
        # per run, and honest bounds for the uptime streaks on /staff/.
        "schedule": 60.0,
    },
}
ANICAST_SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://anicast.online").rstrip("/")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG and not USE_SQLITE
SECURE_HSTS_SECONDS = 31_536_000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
X_FRAME_OPTIONS = "DENY"
METRICS_BEARER_TOKEN = os.environ.get("METRICS_BEARER_TOKEN", "")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "common.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "anicast": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
