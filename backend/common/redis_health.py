"""Read-only Redis signals, independent of the optional telemetry cache."""
from django.conf import settings
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry


def redis_samples():
    if settings.USE_SQLITE:
        return []
    urls = {
        "control": settings.CACHES["default"]["LOCATION"],
        "ephemeral": settings.CACHES["ephemeral"]["LOCATION"],
        "broker": settings.CELERY_BROKER_URL,
    }
    up, used, limit, evictions = [], [], [], []
    for role, url in urls.items():
        try:
            with Redis.from_url(
                url, socket_connect_timeout=0.3, socket_timeout=0.3,
                retry=Retry(NoBackoff(), 0),
            ) as client:
                memory = client.info("memory")
                stats = client.info("stats")
            up.append(f'anicast_redis_up{{role="{role}"}} 1')
            used.append(f'anicast_redis_used_memory_bytes{{role="{role}"}} {int(memory["used_memory"])}')
            limit.append(f'anicast_redis_maxmemory_bytes{{role="{role}"}} {int(memory["maxmemory"])}')
            evictions.append(f'anicast_redis_evicted_keys_total{{role="{role}"}} {int(stats["evicted_keys"])}')
        except Exception:
            # Never emit connection URLs or exception strings containing secrets.
            up.append(f'anicast_redis_up{{role="{role}"}} 0')
    return [
        ("anicast_redis_up", "Redis role reachable at scrape time.", "gauge", up),
        ("anicast_redis_used_memory_bytes", "Redis allocated memory.", "gauge", used),
        ("anicast_redis_maxmemory_bytes", "Redis configured maxmemory.", "gauge", limit),
        ("anicast_redis_evicted_keys_total", "Redis keys evicted by memory policy.", "counter", evictions),
    ]
