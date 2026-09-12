#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
# Secrets must never enter git: live env files and backups stay host-private.
# This fails the gate if a tracked path looks like a secret carrier.
if git -C "$root" ls-files | grep -Eq '(^|/)\.env$|(^|/)secrets/|(^|/)credentials/|(^|/)backups/'; then
    echo "tracked secret carrier found: env/secrets/backups must stay untracked" >&2
    git -C "$root" ls-files | grep -E '(^|/)\.env$|(^|/)secrets/|(^|/)credentials/|(^|/)backups/' >&2 || true
    exit 1
fi
python3 -m unittest discover -s "$root/scripts/tests" -p 'test_capacity_report.py'
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
    --entrypoint promtool prom/prometheus:v3.14.0@sha256:5ce7540c3c00ef4ab0c9d2c995c6a5b9c421f44b4a115d97a2c7af3b1c21cbb0 check config /etc/prometheus/prometheus.yml
docker run --rm \
    -v "$root/infra/monitoring/alertmanager.yml":/etc/alertmanager/alertmanager.yml:ro \
    -v "$secrets_tmp/telegram-token":/etc/alertmanager/secrets/telegram-token:ro \
    -v "$secrets_tmp/telegram-chat-id":/etc/alertmanager/secrets/telegram-chat-id:ro \
    --entrypoint amtool prom/alertmanager:v0.34.0@sha256:690c7b525f4367aa91f73e2f91c632206d32e97c6384bdbf2fb7a861b420340d check-config /etc/alertmanager/alertmanager.yml

"$root/scripts/tests/deploy_rollback_test.sh"
