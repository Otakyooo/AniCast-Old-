#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/bin-fail" "$tmp/bin-ok" "$tmp/state" "$tmp/state-ok"

# Failing stub: containers created from candidate.env never become healthy.
cat >"$tmp/bin-fail/docker" <<'EOF'
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
# Passing stub: every container reports healthy, so deployment succeeds.
cat >"$tmp/bin-ok/docker" <<'EOF'
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
    container-*) printf 'healthy\n' ;;
esac
exit 0
EOF
for bin in bin-fail bin-ok; do
    cat >"$tmp/$bin/curl" <<'EOF'
#!/bin/sh
exit 0
EOF
done
chmod +x "$tmp"/bin-fail/* "$tmp"/bin-ok/*

cat >"$tmp/state/current.env" <<EOF
FRONTEND_IMAGE=registry.example/anicast-frontend@sha256:old
ANICAST_ENV_FILE=$root/infra/vps/env.example
EOF
cp "$tmp/state/current.env" "$tmp/state-ok/current.env"
cat >"$tmp/release.env" <<EOF
FRONTEND_IMAGE=registry.example/anicast-frontend@sha256:new
ANICAST_ENV_FILE=$root/infra/vps/env.example
EOF

if PATH="$tmp/bin-fail:$PATH" VERIFY_ATTEMPTS=1 "$root/scripts/deploy.sh" vps "$tmp/release.env" "$tmp/state"; then
    echo "deployment unexpectedly succeeded" >&2
    exit 1
fi
grep -q 'sha256:old' "$tmp/state/current.env"
grep -q 'sha256:new' "$tmp/state/failed.env"
[ ! -d "$tmp/state/deploy.lock" ]
echo "automatic rollback test passed"

# Happy path: a passing health gate promotes the candidate to current.env,
# keeps the old release as previous.env and releases the lock.
PATH="$tmp/bin-ok:$PATH" VERIFY_ATTEMPTS=1 \
    "$root/scripts/deploy.sh" vps "$tmp/release.env" "$tmp/state-ok"
grep -q 'sha256:new' "$tmp/state-ok/current.env"
grep -q 'sha256:old' "$tmp/state-ok/previous.env"
[ ! -e "$tmp/state-ok/candidate.env" ]
[ ! -d "$tmp/state-ok/deploy.lock" ]
echo "deployment promotion test passed"
