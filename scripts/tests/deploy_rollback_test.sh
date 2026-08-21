#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/bin" "$tmp/state"

cat >"$tmp/bin/docker" <<'EOF'
#!/bin/sh
env_file=
last=
while [ "$#" -gt 0 ]; do
    [ "$last" = --env-file ] && env_file=$1
    last=$1
    shift
done
case "$last" in
    frontend|caddy) printf 'container-%s\n' "$(basename "$env_file")" ;;
    container-candidate.env) printf 'unhealthy\n' ;;
    container-rollback.env) printf 'healthy\n' ;;
esac
exit 0
EOF
cat >"$tmp/bin/curl" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$tmp/bin/docker" "$tmp/bin/curl"

cat >"$tmp/state/current.env" <<EOF
FRONTEND_IMAGE=registry.example/anicast-frontend@sha256:old
ANICAST_ENV_FILE=$root/infra/vps/env.example
EOF
cat >"$tmp/release.env" <<EOF
FRONTEND_IMAGE=registry.example/anicast-frontend@sha256:new
ANICAST_ENV_FILE=$root/infra/vps/env.example
EOF

if PATH="$tmp/bin:$PATH" VERIFY_ATTEMPTS=1 "$root/scripts/deploy.sh" vps "$tmp/release.env" "$tmp/state"; then
    echo "deployment unexpectedly succeeded" >&2
    exit 1
fi
grep -q 'sha256:old' "$tmp/state/current.env"
grep -q 'sha256:new' "$tmp/state/failed.env"
[ ! -d "$tmp/state/deploy.lock" ]
echo "automatic rollback test passed"
