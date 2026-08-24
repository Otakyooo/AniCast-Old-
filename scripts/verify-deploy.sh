#!/bin/sh
set -eu

stack=${1:?usage: verify-deploy.sh mainserver|vps [env-file]}
env_file=${2:-}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)

case "$stack" in
    mainserver) project=${ANICAST_PROJECT_MAINSERVER:-anicast-mainserver} ;;
    vps) project=${ANICAST_PROJECT_VPS:-anicast-vps} ;;
    *) echo "unknown stack: $stack" >&2; exit 2 ;;
esac

compose() {
    if [ -n "$env_file" ]; then
        docker compose --project-name "$project" --env-file "$env_file" -f "$root/infra/$stack/compose.yml" "$@"
    else
        docker compose --project-name "$project" -f "$root/infra/$stack/compose.yml" "$@"
    fi
}

wait_healthy() {
    service=$1
    attempts=${2:-${VERIFY_ATTEMPTS:-30}}
    while [ "$attempts" -gt 0 ]; do
        container=$(compose ps -q "$service")
        health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)
        [ "$health" = healthy ] && return 0
        attempts=$((attempts - 1))
        sleep 2
    done
    echo "service $service did not become healthy" >&2
    compose ps >&2
    return 1
}

case "$stack" in
    mainserver)
        for service in postgres redis backend celery-worker celery-beat; do wait_healthy "$service"; done
        compose exec -T backend python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://localhost:8000/health/ready', headers={'X-Forwarded-Proto':'https'}), timeout=5)"
        compose exec -T celery-worker celery -A config inspect ping --timeout 10 | grep -q pong
        ;;
    vps)
        wait_healthy frontend
        wait_healthy caddy
        curl --fail --silent --show-error --max-time 10 http://127.0.0.1:3000/ >/dev/null
        ;;
    *) echo "unknown stack: $stack" >&2; exit 2 ;;
esac
