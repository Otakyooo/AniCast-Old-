#!/bin/sh
set -eu
image=${1:?usage: redis_isolation_test.sh tested-backend-image}
root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
prefix=anicast-redis-test-$$
network=$prefix-network
control=$prefix-control
cache=$prefix-cache
broker=$prefix-broker
created_network=0; created_control=0; created_cache=0; created_broker=0
cleanup() {
    [ "$created_cache" = 0 ] || docker rm -f -v "$cache" >/dev/null
    [ "$created_control" = 0 ] || docker rm -f -v "$control" >/dev/null
    [ "$created_broker" = 0 ] || docker rm -f -v "$broker" >/dev/null
    [ "$created_network" = 0 ] || docker network rm "$network" >/dev/null
}
trap cleanup EXIT INT TERM
docker network create --internal "$network" >/dev/null
created_network=1
for role in control cache broker; do
    case "$role" in control) name=$control; policy=noeviction ;; cache) name=$cache; policy=allkeys-lru ;; broker) name=$broker; policy=noeviction ;; esac
    docker run -d --name "$name" --network "$network" --memory 48m redis:7-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf \
        redis-server --save '' --appendonly no --maxmemory 4mb --maxmemory-policy "$policy" \
        --requirepass isolated-test-password >/dev/null
    case "$role" in control) created_control=1 ;; cache) created_cache=1 ;; broker) created_broker=1 ;; esac
    attempts=20
    until docker exec -e REDISCLI_AUTH=isolated-test-password "$name" redis-cli ping | grep -q PONG; do
        attempts=$((attempts - 1)); [ "$attempts" -gt 0 ] || exit 1
        sleep 1
    done
done
probe() {
    docker run --rm --network "$network" --memory 192m --cpus 0.5 \
        -e TEST_CONTROL_HOST="$control" -e TEST_CACHE_HOST="$cache" \
        -e TEST_BROKER_HOST="$broker" \
        -v "$root/scripts/tests/redis_isolation_test.py:/test.py:ro" \
        "$image" python /test.py "$1"
}
probe fill
docker stop "$cache" >/dev/null
probe outage
probe control-full
docker stop "$control" >/dev/null
probe control-down
