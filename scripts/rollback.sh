#!/bin/sh
set -eu
umask 077

stack=${1:?usage: rollback.sh mainserver|vps [state-dir]}
state_dir=${2:-/var/lib/anicast/releases/$stack}
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
previous="$state_dir/previous.env"
current="$state_dir/current.env"

case "$stack" in
    mainserver) project=${ANICAST_PROJECT_MAINSERVER:-mainserver} ;;
    vps) project=${ANICAST_PROJECT_VPS:-vps} ;;
    *) echo "unknown stack: $stack" >&2; exit 2 ;;
esac

[ -f "$previous" ] || { echo "no previous release manifest: $previous" >&2; exit 1; }
cp "$previous" "$state_dir/rollback.env"
case "$stack" in mainserver) image_var=BACKEND_IMAGE; service=backend ;; vps) image_var=FRONTEND_IMAGE; service=frontend ;; esac
image=$(sed -n "s/^$image_var=//p" "$previous")
case "$image" in
    sha256:*)
        # A registry release may roll back to a retained pre-registry image.
        printf '%s' "$image" | grep -Eq '^sha256:[a-f0-9]{64}$' || exit 2
        docker image inspect "$image" >/dev/null ;;
    *@sha256:*)
        printf '%s' "$image" | grep -Eq '^[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}$' || exit 2
        if [ "${ANICAST_LOCAL_IMAGES:-0}" != 1 ]; then
            docker compose --project-name "$project" --env-file "$state_dir/rollback.env" -f "$root/infra/$stack/compose.yml" pull "$service"
        fi ;;
    *) echo "invalid rollback image" >&2; exit 2 ;;
esac
sh "$root/scripts/start-release.sh" "$stack" "$state_dir/rollback.env"
"$root/scripts/verify-deploy.sh" "$stack" "$state_dir/rollback.env"
if [ ! -f "$state_dir/failed.env" ] && [ -f "$current" ]; then cp "$current" "$state_dir/failed.env"; fi
mv "$state_dir/rollback.env" "$current"
echo "rollback verified for $stack; database was not restored"
