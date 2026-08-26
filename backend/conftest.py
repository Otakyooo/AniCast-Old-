import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    # The anon rate limit lives in the shared default cache, so without a reset
    # the per-minute budget leaks across tests and makes suites order-dependent.
    cache.clear()
    yield
    cache.clear()
