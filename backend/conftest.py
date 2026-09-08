import pytest
from django.core.cache import caches


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    # Both coordination state and telemetry must be isolated between tests.
    for cache in caches.all():
        cache.clear()
    yield
    for cache in caches.all():
        cache.clear()
