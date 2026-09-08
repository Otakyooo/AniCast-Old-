"""Read-only application checks inside the isolated restore drill network."""
import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from rest_framework.test import APIClient

from catalog.models import Title
from library.models import EpisodeProgress, LibraryEntry

assert not MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes()), "pending migrations in restored dump"
with connection.cursor() as cursor:
    cursor.execute("SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated")
    assert cursor.fetchone()[0] == 0, "unvalidated foreign keys"
    cursor.execute("SELECT has_table_privilege(current_user,'accounts_user','INSERT')")
    assert cursor.fetchone()[0] is False, "drill user must be read-only"
counts = {
    "tables": len(connection.introspection.table_names()),
    "users": get_user_model().objects.count(),
    "titles": Title.objects.count(),
    "library_entries": LibraryEntry.objects.count(),
    "episode_progress": EpisodeProgress.objects.count(),
}
assert counts["tables"] > 20 and counts["users"] > 0 and counts["titles"] > 0
local_caches = {alias: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": alias} for alias in ("default", "ephemeral")}
with override_settings(CACHES=local_caches, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"]):
    client = APIClient()
    for path in ("/health/ready", "/api/v1/titles/?page_size=1"):
        assert client.get(path).status_code == 200, "public API restore smoke failed"
    title = Title.objects.order_by("id").first()
    assert client.get(f"/api/v1/titles/{title.slug}/?episodes_page_size=1").status_code == 200
    client.force_authenticate(user=get_user_model().objects.order_by("id").first())
    for path in ("/api/v1/library/", "/api/v1/history/"):
        assert client.get(path).status_code == 200, "private API restore smoke failed"
print(json.dumps({"counts": counts, "api_smoke": "passed", "database_access": "read-only"}))
