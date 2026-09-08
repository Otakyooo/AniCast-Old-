"""Runs ONLY on disposable Redis containers created by the companion shell script."""
import os
import sys

from kombu import Connection
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry


def test_url(host, database):
    assert host.startswith("anicast-redis-test-")
    return f"redis://:isolated-test-password@{host}:6379/{database}"


control_url = test_url(os.environ["TEST_CONTROL_HOST"], 0)
broker_url = test_url(os.environ["TEST_BROKER_HOST"], 0)
cache_url = test_url(os.environ["TEST_CACHE_HOST"], 0)
options = {"socket_connect_timeout": 0.3, "socket_timeout": 0.3, "retry": Retry(NoBackoff(), 0)}
control = Redis.from_url(control_url, **options)
cache = Redis.from_url(cache_url, **options)
state = Redis.from_url(test_url(os.environ["TEST_CONTROL_HOST"], 2), **options)

if sys.argv[1] == "fill":
    assert control.config_get("maxmemory-policy")["maxmemory-policy"] == "noeviction"
    assert cache.config_get("maxmemory-policy")["maxmemory-policy"] == "allkeys-lru"
    state.set("throttle", "budget-spent", ex=120)
    state.set("lock", "held", ex=120, nx=True)
    # Publish first, then force eviction in the other server.
    with Connection(broker_url) as connection:
        queue = connection.SimpleQueue("isolation-probe")
        queue.put({"probe": "before-fill"})
        for index in range(512):
            cache.set(f"disposable:{index}", b"x" * 32768)
        assert cache.info("stats")["evicted_keys"] > 0
        message = queue.get(block=True, timeout=3)
        assert message.payload == {"probe": "before-fill"}
        message.ack()
        queue.close()
    assert state.get("throttle") == b"budget-spent"
    assert not state.set("lock", "other", ex=120, nx=True)
    print("PASS: cache eviction preserves queued message, throttle and lock")
elif sys.argv[1] == "outage":
    try:
        cache.ping()
    except Exception:
        pass
    else:
        raise AssertionError("cache must be stopped for outage test")
    with Connection(broker_url) as connection:
        queue = connection.SimpleQueue("isolation-probe")
        queue.put({"probe": "cache-down"})
        message = queue.get(block=True, timeout=3)
        assert message.payload == {"probe": "cache-down"}
        message.ack()
        queue.close()
    assert state.get("throttle") == b"budget-spent"
    assert state.get("lock") == b"held"
    print("PASS: cache outage preserves publish/consume and coordination state")
elif sys.argv[1] in ("control-full", "control-down"):
    if sys.argv[1] == "control-full":
        from redis.exceptions import OutOfMemoryError

        for index in range(512):
            try:
                control.set(f"coordination:{index}", b"x" * 32768)
            except OutOfMemoryError:
                break
        else:
            raise AssertionError("coordination must reach its noeviction memory limit")
    else:
        try:
            control.ping()
        except Exception:
            pass
        else:
            raise AssertionError("coordination must be stopped")
    with Connection(broker_url) as connection:
        queue = connection.SimpleQueue("isolation-probe")
        queue.put({"probe": sys.argv[1]})
        message = queue.get(block=True, timeout=3)
        assert message.payload == {"probe": sys.argv[1]}
        message.ack()
        queue.close()
    print("PASS: broker publish/consume survives " + sys.argv[1])
else:
    raise AssertionError("unknown test phase")
