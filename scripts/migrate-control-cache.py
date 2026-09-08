"""Run in a one-off backend container ONLY after stopping all application writers.

SOURCE_CONTROL_URL and TARGET_CONTROL_URL are private environment variables.
Copies Redis DB 2 with original expiry deadlines. Never purges the source.
"""
import os
import time

from redis import Redis

source = Redis.from_url(os.environ["SOURCE_CONTROL_URL"], socket_timeout=5)
target = Redis.from_url(os.environ["TARGET_CONTROL_URL"], socket_timeout=5)
if source.connection_pool.connection_kwargs == target.connection_pool.connection_kwargs:
    raise SystemExit("source and target must differ")
if target.dbsize():
    raise SystemExit("target coordination database must be empty")
copied = expired = 0
for key in source.scan_iter(count=100):
    started = time.monotonic()
    with source.pipeline(transaction=True) as pipeline:
        dump, ttl = pipeline.dump(key).pttl(key).execute()
    if dump is None or ttl == -2:
        expired += 1
        continue
    remaining = ttl - int((time.monotonic() - started) * 1000) if ttl >= 0 else 0
    if ttl >= 0 and remaining <= 0:
        expired += 1
        continue
    target.restore(key, remaining, dump, replace=False)
    if target.dump(key) != dump:
        raise SystemExit("coordination value verification failed")
    copied += 1
print(f"Coordination state copied and verified: {copied}; expired during copy: {expired}")
