"""Read-only HTTP origin for the disposable routing drill, never production."""
import os
from wsgiref.simple_server import make_server, WSGIRequestHandler

assert os.environ.get("POSTGRES_HOST", "").startswith("anicast-restore-")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from django.conf import settings
settings.CACHES = {alias: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": alias} for alias in ("default", "ephemeral")}
settings.SECURE_SSL_REDIRECT = False
settings.ALLOWED_HOSTS = ["testserver"]
from django.core.wsgi import get_wsgi_application
class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass
make_server("0.0.0.0", 8000, get_wsgi_application(), handler_class=QuietHandler).serve_forever()
