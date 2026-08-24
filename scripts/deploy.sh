#!/bin/sh
set -eu

stack=${1:?usage: deploy.sh mainserver|vps release.env [state-dir]}
release=$(realpath "${2:?release manifest is required}")
state_dir=${3:-/var/lib/anicast/releases/$stack}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
lock_dir="$state_dir/deploy.lock"

mkdir -p "$state_dir"
if ! mkdir "$lock_dir" 2>/dev/null; then
    echo "another deployment is active: $lock_dir" >&2
    exit 1
fi
cleanup() { rmdir "$lock_dir" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

case "$stack" in
    mainserver)
        image_var=BACKEND_IMAGE
        # Overridable so the pipeline can adopt the live compose project
        # names (mainserver/vps) instead of spawning parallel stacks with
        # fresh, empty volumes.
        project=${ANICAST_PROJECT_MAINSERVER:-anicast-mainserver} ;;
    vps)
        image_var=FRONTEND_IMAGE
        project=${ANICAST_PROJECT_VPS:-anicast-vps} ;;
    *) echo "unknown stack: $stack" >&2; exit 2 ;;
esac
image=$(sed -n "s/^$image_var=//p" "$release")
[ -n "$image" ] || { echo "$image_var is missing" >&2; exit 2; }
if [ "${ALLOW_MUTABLE_IMAGES:-0}" != 1 ]; then
    case "$image" in *@sha256:*) ;; *) echo "$image_var must use an immutable digest" >&2; exit 2 ;; esac
fi

candidate="$state_dir/candidate.env"
cp "$release" "$candidate"
if [ -f "$state_dir/current.env" ]; then cp "$state_dir/current.env" "$state_dir/previous.env"; fi

rollback_on_failure() {
    code=$?
    [ "$code" -eq 0 ] && return
    echo "deployment verification failed; rolling back application images" >&2
    cp "$candidate" "$state_dir/failed.env" 2>/dev/null || true
    trap cleanup EXIT INT TERM
    if [ -f "$state_dir/previous.env" ]; then "$root/scripts/rollback.sh" "$stack" "$state_dir" || true; fi
    cleanup
    exit "$code"
}
trap rollback_on_failure EXIT

compose() {
    docker compose --project-name "$project" --env-file "$candidate" -f "$root/infra/$stack/compose.yml" "$@"
}

compose config -q
compose pull
if [ "$stack" = mainserver ]; then
    compose up -d postgres redis
    compose run --rm backend python manage.py check --deploy
    compose run --rm backend python manage.py migrate --noinput
fi
compose up -d --no-build --remove-orphans
"$root/scripts/verify-deploy.sh" "$stack" "$candidate"
mv "$candidate" "$state_dir/current.env"
trap cleanup EXIT INT TERM
echo "deployment verified for $stack"
