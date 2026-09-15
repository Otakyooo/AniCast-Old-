#!/bin/sh
# Shared by deployment and rollback: API availability must not wait for bulk.
set -eu

stack=${1:?usage: start-release.sh mainserver|vps release.env}
env_file=${2:?release manifest is required}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
case "$stack" in
    mainserver) project=${ANICAST_PROJECT_MAINSERVER:-mainserver} ;;
    vps) project=${ANICAST_PROJECT_VPS:-vps} ;;
    *) echo "unknown stack: $stack" >&2; exit 2 ;;
esac
compose() {
    docker compose --project-name "$project" --env-file "$env_file" -f "$root/infra/$stack/compose.yml" "$@"
}
if [ "$stack" = mainserver ]; then
    # A named volume arrives root-owned and shadows the image's /app/media, so
    # the app (appuser) cannot write artwork: Docker never applies the image's
    # ownership to a volume, only to the image's own directory. That broke the
    # whole poster and portrait pipeline for two weeks without failing a deploy,
    # because the write error surfaces as a per-item failure inside a task.
    # Realign on every start: `compose down -v`, or a project rename, recreates
    # the volume root-owned and would break it again silently.
    backend_image=$(sed -n 's/^BACKEND_IMAGE=//p' "$env_file" | head -1)
    if [ -n "$backend_image" ]; then
        docker run --rm --user root --entrypoint sh \
            -v "${project}_poster_media:/app/media" \
            "$backend_image" -c 'chown -R appuser /app/media'
    fi
    echo 'Starting API and verifying readiness before worker rollout'
    compose up -d --no-build --wait --wait-timeout 120 postgres redis redis-cache redis-control backend
    echo 'API healthy; updating default worker and scheduler'
    compose up -d --no-build --no-deps --timeout 600 --wait --wait-timeout 120 celery-worker celery-beat
    echo 'Updating bulk worker; API remains available during warm shutdown'
    # Explicit timeout also protects the existing container whose old Compose
    # configuration may still specify 600s. The longest task hard limit is 1800s.
    compose up -d --no-build --no-deps --timeout 1900 --wait --wait-timeout 120 celery-bulk
else
    compose up -d --no-build --remove-orphans
fi
