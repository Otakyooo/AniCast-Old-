#!/bin/sh
set -eu

# AniCast poster media volume restore.
#   restore-posters.sh --verify [archive]   safe check: list, extract and validate a backup
#   restore-posters.sh --force [archive]    destructive: replace the poster volume (stops app containers)
#
# The archive defaults to the newest backups/posters/posters-*.tar.gz as
# produced by scripts/backup-posters.sh. Verification runs entirely on the
# host; --force swaps volume contents through a disposable helper container,
# snapshots the current volume first and probes the serving path afterwards.

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
backup_dir=${BACKUP_DIR:-$root/backups/posters}
volume=${POSTER_VOLUME:-mainserver_poster_media}
helper_image=${HELPER_IMAGE:-alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc}
compose_dir=$root/infra/mainserver
backend_container=${BACKEND_CONTAINER:-mainserver-backend-1}

mode=${1:-}
case "$mode" in
    --verify|--force) ;;
    *) echo "usage: restore-posters.sh --verify|--force [archive]" >&2; exit 2 ;;
esac

if [ $# -ge 2 ]; then
    dump=$(realpath "$2")
else
    dump=$(ls -1t "$backup_dir"/posters-*.tar.gz 2>/dev/null | head -n 1 || true)
    [ -n "$dump" ] || { echo "no archive found in $backup_dir" >&2; exit 2; }
    dump=$(realpath "$dump")
fi
[ -f "$dump" ] || { echo "archive not found: $dump" >&2; exit 2; }

echo "archive: $dump ($(wc -c < "$dump") bytes, created $(date -u -r "$dump" +%Y-%m-%dT%H:%M:%SZ))"

if [ "$mode" = "--verify" ]; then
    # A full listing proves the gzip stream is not truncated.
    tar -tzf "$dump" >/dev/null

    work=$(mktemp -d)
    trap 'rm -rf "$work"' EXIT INT TERM
    tar -xzf "$dump" -C "$work"

    files=$(find "$work" -type f | wc -l)
    [ "$files" -gt 0 ] || {
        echo "verify FAILED: archive contains no poster files" >&2
        exit 1
    }
    empty=$(find "$work" -type f -empty | wc -l)
    [ "$empty" -eq 0 ] || {
        echo "verify FAILED: $empty zero-byte files in archive" >&2
        exit 1
    }
    # Every stored object must be a JPEG (ff d8 ff) or PNG (89 50 4e) —
    # the same magic-byte contract the download pipeline enforces.
    if ! find "$work" -type f -exec sh -c '
        for f do
            magic=$(od -An -tx1 -N3 "$f" | tr -d " \n")
            [ "$magic" = "ffd8ff" ] || [ "$magic" = "89504e" ] || {
                echo "not a JPEG/PNG: $f" >&2
                exit 1
            }
        done
    ' sh {} +; then
        echo "verify FAILED: foreign file types in archive" >&2
        exit 1
    fi
    total=$(du -sk "$work" | cut -f1)
    echo "verify ok: $files posters, ${total} KiB extracted and validated"
    exit 0
fi

printf 'This REPLACES the contents of poster volume %s from the archive.\n' "$volume"
printf 'App containers (backend, celery) will be stopped during the restore.\n'
printf 'The current volume is snapshotted to %s first.\n' "$backup_dir"
printf 'Type the volume name to continue: '
read -r reply
[ "$reply" = "$volume" ] || { echo "aborted" >&2; exit 1; }

stamp=$(date -u +%Y%m%dT%H%M%SZ)
snapshot=$backup_dir/pre-restore-$stamp.tar.gz
docker run --rm --user "$(id -u):$(id -g)" -v "$volume":/data:ro -v "$backup_dir":/backup "$helper_image" \
    tar -czf "/backup/$(basename "$snapshot")" -C /data .
[ -s "$snapshot" ] || { echo "pre-restore snapshot failed; volume left untouched" >&2; exit 1; }
chmod 600 "$snapshot"
echo "current volume saved: $snapshot"

( cd "$compose_dir" && docker compose stop celery-beat celery-worker celery-bulk backend )

docker run --rm -v "$volume":/data -v "$backup_dir":/backup:ro "$helper_image" \
    sh -c 'find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} +; tar -xzf "$1" -C /data; chmod -R a+rX /data' \
    sh "/backup/$(basename "$dump")"

restored=$(docker run --rm -v "$volume":/data:ro "$helper_image" sh -c 'find /data -type f | wc -l')
[ "${restored:-0}" -gt 0 ] || {
    echo "volume looks empty after extraction; restore the snapshot $snapshot and investigate" >&2
    exit 1
}

( cd "$compose_dir" && docker compose up -d )

attempts=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$backend_container" 2>/dev/null)" = healthy ]; do
    attempts=$((attempts + 1))
    if [ "$attempts" -gt 60 ]; then
        echo "backend did not become healthy after restore; check containers manually" >&2
        exit 1
    fi
    sleep 2
done

probe=$(tar -tzf "$dump" | grep -v '/$' | head -n 1 | sed 's|^\./||; s|^.*/||')
if ! docker exec "$backend_container" python -c \
    "import sys, urllib.request; code = urllib.request.urlopen(urllib.request.Request('http://localhost:8000/api/v1/media/posters/$probe', headers={'X-Forwarded-Proto': 'https'}), timeout=5).status; sys.exit(0 if code == 200 else 1)"; then
    echo "serving probe failed for /api/v1/media/posters/$probe; backend is up but check MEDIA settings" >&2
    exit 1
fi

echo "restore complete: $restored posters back in $volume (snapshot kept: $snapshot)"
