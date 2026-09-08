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
if [ "${ANICAST_LOCAL_IMAGES:-0}" != 1 ]; then
    docker compose --project-name "$project" --env-file "$state_dir/rollback.env" -f "$root/infra/$stack/compose.yml" pull
fi
docker compose --project-name "$project" --env-file "$state_dir/rollback.env" -f "$root/infra/$stack/compose.yml" up -d --no-build --remove-orphans
"$root/scripts/verify-deploy.sh" "$stack" "$state_dir/rollback.env"
if [ ! -f "$state_dir/failed.env" ] && [ -f "$current" ]; then cp "$current" "$state_dir/failed.env"; fi
mv "$state_dir/rollback.env" "$current"
echo "rollback verified for $stack; database was not restored"
