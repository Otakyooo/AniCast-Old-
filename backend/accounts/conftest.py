import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_auth_throttle_cache():
    cache.clear()
    yield
    cache.clear()
