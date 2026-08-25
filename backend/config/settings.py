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
DATABASES: dict[str, Any] = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ.get("POSTGRES_DB", "anicast"), "USER": os.environ.get("POSTGRES_USER", "anicast"), "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "anicast-dev"), "HOST": os.environ.get("POSTGRES_HOST", "postgres"), "PORT": os.environ.get("POSTGRES_PORT", "5432")}}
USE_SQLITE = os.environ.get("DJANGO_DATABASE_URL", "").startswith("sqlite")
if USE_SQLITE:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
if SECRET_KEY == "dev-only-change-me" and not DEBUG and not USE_SQLITE and not os.environ.get("DJANGO_ALLOW_DEV_SECRET"):
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
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_SAVE_EVERY_REQUEST = True
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x]
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "auth": "10/min",
        "playback": "30/min",
        "telegram_challenge": "20/min",
    },
}
if USE_SQLITE:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.environ.get("CACHE_URL", "redis://redis:6379/2")}}
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_NOTIFY_BOT_TOKEN = os.environ.get("TELEGRAM_NOTIFY_BOT_TOKEN", "")
TELEGRAM_NOTIFY_BOT_USERNAME = os.environ.get("TELEGRAM_NOTIFY_BOT_USERNAME", "")
TELEGRAM_NOTIFY_WEBHOOK_SECRET = os.environ.get("TELEGRAM_NOTIFY_WEBHOOK_SECRET", "")
KODIK_API_TOKEN = os.environ.get("KODIK_API_TOKEN", "")
PLAYBACK_URL_TTL_SECONDS = int(os.environ.get("PLAYBACK_URL_TTL_SECONDS", "60"))
POSTERS_MEDIA_ROOT = Path(os.environ.get("POSTERS_MEDIA_ROOT", str(BASE_DIR / "media" / "posters")))
POSTERS_PUBLIC_BASE = os.environ.get("POSTERS_PUBLIC_BASE", "https://anicast.online").rstrip("/")
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TASK_ROUTES = {
    "push.tasks.dispatch_episode_notifications": {"queue": "notifications"},
    "push.tasks.dispatch_event_notifications": {"queue": "notifications"},
    "push.tasks.send_schedule_digest": {"queue": "notifications"},
    "catalog.tasks.check_provider_sources": {"queue": "providers"},
    "catalog.tasks.refresh_title_posters": {"queue": "posters"},
    "catalog.tasks.sync_kodik_library": {"queue": "providers"},
    "common.tasks.probe_site_availability": {"queue": "default"},
}
CELERY_TASK_SOFT_TIME_LIMIT = 540
CELERY_TASK_TIME_LIMIT = 570
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULE = {
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
