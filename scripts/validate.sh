#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
for script in "$root"/scripts/*.sh "$root"/scripts/tests/*.sh; do sh -n "$script"; done
docker compose --env-file "$root/infra/mainserver/env.example" -f "$root/infra/mainserver/compose.yml" config -q
docker compose --env-file "$root/infra/vps/env.example" -f "$root/infra/vps/compose.yml" config -q
if grep -Eq 'handle[[:space:]]+/(internal/)?metrics|reverse_proxy.+9090' "$root/infra/vps/Caddyfile"; then
    echo "metrics must not be publicly routed by Caddy" >&2
    exit 1
fi
"$root/scripts/tests/deploy_rollback_test.sh"
