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
printf '%s\n' "$*" >> "${ANICAST_DOCKER_LOG:-/dev/null}"
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
FRONTEND_IMAGE=registry.example/anicast-frontend@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
ANICAST_ENV_FILE=$root/infra/vps/env.example
EOF
cp "$tmp/state/current.env" "$tmp/state-ok/current.env"
cat >"$tmp/release.env" <<EOF
FRONTEND_IMAGE=registry.example/anicast-frontend@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
ANICAST_ENV_FILE=$root/infra/vps/env.example
EOF

if PATH="$tmp/bin-fail:$PATH" VERIFY_ATTEMPTS=1 "$root/scripts/deploy.sh" vps "$tmp/release.env" "$tmp/state"; then
    echo "deployment unexpectedly succeeded" >&2
    exit 1
fi
grep -q 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$tmp/state/current.env"
grep -q 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' "$tmp/state/failed.env"
[ ! -d "$tmp/state/deploy.lock" ]
echo "automatic rollback test passed"

# Happy path: a passing health gate promotes the candidate to current.env,
# keeps the old release as previous.env and releases the lock.
PATH="$tmp/bin-ok:$PATH" VERIFY_ATTEMPTS=1 \
    "$root/scripts/deploy.sh" vps "$tmp/release.env" "$tmp/state-ok"
grep -q 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' "$tmp/state-ok/current.env"
grep -q 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$tmp/state-ok/previous.env"
[ ! -e "$tmp/state-ok/candidate.env" ]
[ ! -d "$tmp/state-ok/deploy.lock" ]
echo "deployment promotion test passed"

# A cold deployment must not silently use a stale previous.env or invent a
# rollback image. No application may be promoted without a captured baseline.
mkdir -p "$tmp/state-cold"
if PATH="$tmp/bin-ok:$PATH" "$root/scripts/deploy.sh" vps "$tmp/release.env" "$tmp/state-cold"; then
    echo "deployment without a live baseline unexpectedly succeeded" >&2
    exit 1
fi
[ ! -f "$tmp/state-cold/current.env" ]
[ ! -d "$tmp/state-cold/deploy.lock" ]
echo "missing baseline rejected"

printf 'FRONTEND_IMAGE=registry.example/anicast-frontend:latest\n' > "$tmp/mutable.env"
if PATH="$tmp/bin-ok:$PATH" "$root/scripts/deploy.sh" vps "$tmp/mutable.env" "$tmp/state-ok"; then
    echo "mutable release unexpectedly accepted" >&2
    exit 1
fi
grep -q 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' "$tmp/state-ok/current.env"
echo "mutable image rejected without changing current release"

local_id=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
printf 'FRONTEND_IMAGE=%s\n' "$local_id" > "$tmp/local.env"
if PATH="$tmp/bin-ok:$PATH" "$root/scripts/deploy.sh" vps "$tmp/local.env" "$tmp/state-ok"; then
    echo "local image accepted without opt-in" >&2
    exit 1
fi
PATH="$tmp/bin-ok:$PATH" ANICAST_LOCAL_IMAGES=1 ANICAST_DOCKER_LOG="$tmp/local-docker.log" \
    "$root/scripts/deploy.sh" vps "$tmp/local.env" "$tmp/state-ok"
grep -q "$local_id" "$tmp/state-ok/current.env"
grep -q -- '--project-name vps' "$tmp/local-docker.log"
if grep -q ' pull$' "$tmp/local-docker.log"; then
    echo "local image deployment attempted registry pull" >&2
    exit 1
fi
echo "local immutable image deployment passed"

# Reject malformed registry digests before a release is promoted.
printf 'FRONTEND_IMAGE=registry.example/anicast-frontend@sha256:sha256:broken\n' > "$tmp/bad-digest.env"
if PATH="$tmp/bin-ok:$PATH" "$root/scripts/deploy.sh" vps "$tmp/bad-digest.env" "$tmp/state-ok"; then
    echo "malformed digest unexpectedly accepted" >&2; exit 1
fi
# A normal registry-mode rollback can use a retained local baseline without pull.
printf 'FRONTEND_IMAGE=%s\n' "$local_id" > "$tmp/state-ok/previous.env"
: > "$tmp/rollback-local.log"
PATH="$tmp/bin-ok:$PATH" ANICAST_DOCKER_LOG="$tmp/rollback-local.log" \
    "$root/scripts/rollback.sh" vps "$tmp/state-ok"
if grep -q ' pull' "$tmp/rollback-local.log"; then
    echo "local rollback unexpectedly attempted registry pull" >&2; exit 1
fi
echo "registry-to-local rollback passed"

# MainServer state machine: a bulk drain is allowed only after the candidate API
# has passed its readiness gate. Failures exercise the real rollback entry point.
mkdir -p "$tmp/bin-main"
cat >"$tmp/bin-main/docker" <<'EOF'
#!/bin/sh
set -eu
command=$*
env_file=
last=
for arg in "$@"; do
    [ "$last" != --env-file ] || env_file=$arg
    last=$arg
done
release=$(basename "$env_file")
case "$command" in
    *' up '*backend) phase=api ;;
    *' up '*celery-beat) phase=default ;;
    *' up '*celery-bulk) phase=bulk ;;
    *' up '*--remove-orphans) echo 'unphased MainServer rollout' >&2; exit 91 ;;
    *' ps -q '*) echo "container-$last"; exit ;;
    *'inspect --format '*) echo healthy; exit ;;
    *' exec '*) echo pong; exit ;;
    *) exit 0 ;;
esac
printf '%s %s begin\n' "$release" "$phase" >> "$ANICAST_PHASE_LOG"
if [ "$phase" != api ]; then
    [ "$(cat "$ANICAST_API_READY")" = "$release" ] || exit 92
    case "$command" in *' --no-deps '*) ;; *) exit 93 ;; esac
fi
if [ "$phase" = bulk ]; then
    case "$command" in *' --timeout 1900 '*) ;; *) exit 94 ;; esac
fi
if [ "$release" = candidate.env ] && [ "$phase" = "${ANICAST_FAIL_PHASE:-none}" ]; then
    exit 95
fi
if [ "$phase" = api ]; then
    case "$command" in *' --wait --wait-timeout 120 '*) ;; *) exit 96 ;; esac
    printf '%s\n' "$release" > "$ANICAST_API_READY"
fi
printf '%s %s healthy\n' "$release" "$phase" >> "$ANICAST_PHASE_LOG"
EOF
chmod +x "$tmp/bin-main/docker"
for failure in none api default bulk; do
    main_state="$tmp/main-$failure"
    mkdir -p "$main_state"
    printf 'BACKEND_IMAGE=registry.example/backend@sha256:%s\n' \
        aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa > "$main_state/current.env"
    printf 'BACKEND_IMAGE=registry.example/backend@sha256:%s\n' \
        bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb > "$main_state/release.env"
    if PATH="$tmp/bin-main:$PATH" VERIFY_ATTEMPTS=1 ANICAST_FAIL_PHASE="$failure" \
        ANICAST_PHASE_LOG="$main_state/phases" ANICAST_API_READY="$main_state/api-ready" \
        "$root/scripts/deploy.sh" mainserver "$main_state/release.env" "$main_state"; then
        [ "$failure" = none ] || { echo 'failed phase was promoted' >&2; exit 1; }
        grep -q bbbbbbbb "$main_state/current.env"
    else
        [ "$failure" != none ] || exit 1
        grep -q aaaaaaaa "$main_state/current.env"
        grep -q bbbbbbbb "$main_state/failed.env"
        grep -q 'rollback.env api healthy' "$main_state/phases"
        grep -q 'rollback.env bulk healthy' "$main_state/phases"
    fi
    grep -q 'candidate.env api begin' "$main_state/phases"
    if [ "$failure" = api ]; then
        ! grep -Eq 'candidate.env (default|bulk)' "$main_state/phases"
    elif [ "$failure" = default ]; then
        ! grep -q 'candidate.env bulk' "$main_state/phases"
    else
        grep -q 'candidate.env bulk begin' "$main_state/phases"
    fi
    [ ! -d "$main_state/deploy.lock" ]
done
echo 'MainServer API-first rollout, phase failures and phased rollback passed'
