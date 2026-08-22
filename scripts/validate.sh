#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
for script in "$root"/scripts/*.sh "$root"/scripts/tests/*.sh; do sh -n "$script"; done
docker compose --env-file "$root/infra/mainserver/env.example" -f "$root/infra/mainserver/compose.yml" config -q
docker compose --env-file "$root/infra/vps/env.example" -f "$root/infra/vps/compose.yml" config -q
docker compose -f "$root/infra/monitoring/compose.yml" config -q
if grep -Eq 'handle[[:space:]]+/(internal/)?metrics|reverse_proxy.+9090' "$root/infra/vps/Caddyfile"; then
    echo "metrics must not be publicly routed by Caddy" >&2
    exit 1
fi

# promtool/amtool verify file references, so mount placeholder secrets that
# mirror infra/monitoring/secrets/ without exposing real values.
secrets_tmp=$(mktemp -d)
cleanup() { rm -rf "$secrets_tmp"; }
trap cleanup EXIT INT TERM
printf 'validate-placeholder\n' > "$secrets_tmp/metrics-token"
printf '000000:placeholder\n' > "$secrets_tmp/telegram-token"
printf '0\n' > "$secrets_tmp/telegram-chat-id"
docker run --rm \
    -v "$root/infra/monitoring/prometheus.yml":/etc/prometheus/prometheus.yml:ro \
    -v "$root/infra/monitoring/rules":/etc/prometheus/rules:ro \
    -v "$secrets_tmp/metrics-token":/etc/prometheus/secrets/metrics-token:ro \
    --entrypoint promtool prom/prometheus:v3.14.0 check config /etc/prometheus/prometheus.yml
docker run --rm \
    -v "$root/infra/monitoring/alertmanager.yml":/etc/alertmanager/alertmanager.yml:ro \
    -v "$secrets_tmp/telegram-token":/etc/alertmanager/secrets/telegram-token:ro \
    -v "$secrets_tmp/telegram-chat-id":/etc/alertmanager/secrets/telegram-chat-id:ro \
    --entrypoint amtool prom/alertmanager:v0.34.0 check-config /etc/alertmanager/alertmanager.yml

"$root/scripts/tests/deploy_rollback_test.sh"
