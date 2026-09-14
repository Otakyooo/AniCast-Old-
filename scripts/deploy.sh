#!/bin/sh
set -eu
umask 077

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
        project=${ANICAST_PROJECT_MAINSERVER:-mainserver} ;;
    vps)
        image_var=FRONTEND_IMAGE
        project=${ANICAST_PROJECT_VPS:-vps} ;;
    *) echo "unknown stack: $stack" >&2; exit 2 ;;
esac
image=$(sed -n "s/^$image_var=//p" "$release")
[ -n "$image" ] || { echo "$image_var is missing" >&2; exit 2; }
case "$image" in
    *@sha256:*)
        printf '%s' "$image" | grep -Eq '^[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}$' || { echo "invalid registry digest" >&2; exit 2; } ;;
    sha256:*)
        [ "${ANICAST_LOCAL_IMAGES:-0}" = 1 ] || { echo "local images require ANICAST_LOCAL_IMAGES=1" >&2; exit 2; }
        printf '%s' "$image" | grep -Eq '^sha256:[a-f0-9]{64}$' || exit 2
        docker image inspect "$image" >/dev/null ;;
    *) echo "$image_var must use an immutable registry digest or an explicitly allowed local image ID" >&2; exit 2 ;;
esac

candidate="$state_dir/candidate.env"
cp "$release" "$candidate"
[ -f "$state_dir/current.env" ] || { echo "bootstrap current.env from the live image before deploying" >&2; exit 2; }
# Keep three rollback generations: a second broken release must not erase the
# last known-good manifest. Rotation is cheap and host-private.
if [ -f "$state_dir/previous-2.env" ]; then cp "$state_dir/previous-2.env" "$state_dir/previous-3.env"; fi
if [ -f "$state_dir/previous.env" ]; then cp "$state_dir/previous.env" "$state_dir/previous-2.env"; fi
cp "$state_dir/current.env" "$state_dir/previous.env"

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
if [ "${ANICAST_LOCAL_IMAGES:-0}" != 1 ]; then
    case "$stack" in mainserver) compose pull backend ;; vps) compose pull frontend ;; esac
fi
if [ "$stack" = mainserver ]; then
    compose up -d postgres redis redis-cache redis-control
    compose run --rm backend python manage.py check --deploy --fail-level WARNING
    compose run --rm backend python manage.py migrate --noinput
fi
sh "$root/scripts/start-release.sh" "$stack" "$candidate"
"$root/scripts/verify-deploy.sh" "$stack" "$candidate"
mv "$candidate" "$state_dir/current.env"
# The recovery kit is built by the deployment account, which cannot read a
# 0600 root-owned manifest. Keep the promoted manifest group-readable so the
# kit records the live release instead of a stale copy. Never fail a deploy
# over this.
for d in "$state_dir" "$(dirname "$state_dir")" "$(dirname "$(dirname "$state_dir")")"; do
    chgrp lama_admin "$d" 2>/dev/null || true
    chmod 0750 "$d" 2>/dev/null || true
done
chgrp lama_admin "$state_dir/current.env" 2>/dev/null || true
chmod 0640 "$state_dir/current.env" 2>/dev/null || true
trap cleanup EXIT INT TERM
echo "deployment verified for $stack"
