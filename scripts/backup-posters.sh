#!/bin/sh
set -eu
umask 077

# AniCast poster media volume backup: verified local tarball with retention
# and an encrypted offsite copy on Google Drive (rclone crypt remote).
# The pipeline self-heals a lost volume from remote sources, but a backup
# restores full quality instantly instead of re-probing Jikan for hours.

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
mkdir -p "$root/backups"
exec 9>"$root/backups/.backup-posters.lock"
flock -n 9 || { echo "another posters backup is active" >&2; exit 75; }
backup_dir=${BACKUP_DIR:-$root/backups/posters}
rclone_bin=${RCLONE_BIN:-$HOME/.local/bin/rclone}
rclone_remote=${RCLONE_REMOTE:-gdcrypt:posters}
volume=${POSTER_VOLUME:-mainserver_poster_media}
helper_image=${HELPER_IMAGE:-alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc}
retention_days=${RETENTION_DAYS:-30}
offsite_min_age_days=${OFFSITE_MIN_AGE_DAYS:-90}

ops_env=$root/infra/monitoring/.env
# See backup-db.sh: Telegram is unreachable from this host, so the alert path goes
# through the relay inside the tunnel.
telegram_api=${TELEGRAM_API_BASE_URL:-http://10.78.0.1:8443}
alert() {
    message=$1
    failure_reported=1
    echo "$message" >&2
    [ "${BACKUP_NOTIFY:-1}" = 1 ] || return 0
    [ -f "$ops_env" ] || return 0
    token=$(sed -n 's/^OPS_TELEGRAM_BOT_TOKEN=//p' "$ops_env")
    chat_id=$(sed -n 's/^OPS_TELEGRAM_CHAT_ID=//p' "$ops_env")
    [ -n "$token" ] && [ -n "$chat_id" ] || return 0
    curl -fsS --max-time 10 -X POST "${telegram_api%/}/bot${token}/sendMessage" \
        -d chat_id="$chat_id" --data-urlencode text="$message" >/dev/null 2>&1 || true
}

failure_reported=0
backup_exit() {
    code=$?
    if [ "$code" -ne 0 ] && [ "$failure_reported" = 0 ]; then
        alert "Anicast posters backup failed; inspect the private backup log"
    fi
    exit "$code"
}
trap backup_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dump=$backup_dir/posters-$stamp.tar.gz

files_before=$(docker run --rm --memory 96m --cpus 0.4 --network none -v "$volume":/data:ro "$helper_image" sh -c 'find /data -type f | wc -l')
docker run --rm --memory 96m --cpus 0.4 --network none --user "$(id -u):$(id -g)" -v "$volume":/data:ro -v "$backup_dir":/backup "$helper_image" \
    tar -czf "/backup/$(basename "$dump")" -C /data .
[ -s "$dump" ] || {
    alert "AniCast poster backup FAILED: empty archive ($volume)"
    exit 1
}

files_archive=$(tar -tzf "$dump" | grep -cv '/$' || true)
if [ "${files_before:-0}" -gt 0 ] && [ "$files_archive" -lt "$files_before" ]; then
    alert "AniCast poster backup FAILED: $files_archive of $files_before files archived"
    exit 1
fi
chmod 600 "$dump"

find "$backup_dir" -name 'posters-*.tar.gz' -mtime "+$retention_days" -delete

sha256sum "$dump" > "$dump.sha256"

if [ -x "$rclone_bin" ] && "$rclone_bin" listremotes 2>/dev/null | grep -q '^gdcrypt:$'; then
    if "$rclone_bin" copy --quiet "$dump" "$rclone_remote"; then
        "$rclone_bin" copy --quiet "$dump.sha256" "$rclone_remote"
        "$rclone_bin" delete --quiet --min-age "${offsite_min_age_days}d" "$rclone_remote"
        echo "offsite copy uploaded"
    else
        alert "AniCast poster backup: rclone offsite upload failed"
        exit 1
    fi
else
    [ "${ALLOW_LOCAL_BACKUP:-0}" = 1 ] || {
        alert "Anicast poster backup FAILED: offsite remote unavailable"
        exit 1
    }
fi

if [ "${ALLOW_LOCAL_BACKUP:-0}" != 1 ]; then
    printf '%s\n' "$stamp" > "$backup_dir/last_offsite_backup"
fi

echo "poster volume backup verified: $dump ($(wc -c < "$dump") bytes, $files_archive files)"
