import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_community_throttle_cache():
    cache.clear()
    yield
    cache.clear()
