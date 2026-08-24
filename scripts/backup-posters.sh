#!/bin/sh
set -eu

# AniCast poster media volume backup: verified local tarball with retention
# and an encrypted offsite copy on Google Drive (rclone crypt remote).
# The pipeline self-heals a lost volume from remote sources, but a backup
# restores full quality instantly instead of re-probing Jikan for hours.

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
backup_dir=${BACKUP_DIR:-$root/backups/posters}
rclone_bin=${RCLONE_BIN:-$HOME/.local/bin/rclone}
rclone_remote=${RCLONE_REMOTE:-gdcrypt:posters}
volume=${POSTER_VOLUME:-mainserver_poster_media}
helper_image=${HELPER_IMAGE:-alpine:3.20}
retention_days=${RETENTION_DAYS:-30}
offsite_min_age_days=${OFFSITE_MIN_AGE_DAYS:-90}

ops_env=$root/infra/monitoring/.env
alert() {
    message=$1
    echo "$message" >&2
    [ -f "$ops_env" ] || return 0
    token=$(sed -n 's/^OPS_TELEGRAM_BOT_TOKEN=//p' "$ops_env")
    chat_id=$(sed -n 's/^OPS_TELEGRAM_CHAT_ID=//p' "$ops_env")
    [ -n "$token" ] && [ -n "$chat_id" ] || return 0
    curl -fsS --max-time 10 -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -d chat_id="$chat_id" --data-urlencode text="$message" >/dev/null 2>&1 || true
}

mkdir -p "$backup_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dump=$backup_dir/posters-$stamp.tar.gz

files_before=$(docker run --rm -v "$volume":/data:ro "$helper_image" sh -c 'find /data -type f | wc -l')
docker run --rm --user "$(id -u):$(id -g)" -v "$volume":/data:ro -v "$backup_dir":/backup "$helper_image" \
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

if [ -x "$rclone_bin" ] && "$rclone_bin" listremotes 2>/dev/null | grep -q '^gdcrypt:$'; then
    if "$rclone_bin" copy --quiet "$dump" "$rclone_remote"; then
        "$rclone_bin" delete --quiet --min-age "${offsite_min_age_days}d" "$rclone_remote" || true
        echo "offsite copy uploaded"
    else
        alert "AniCast poster backup: rclone offsite upload failed"
    fi
fi

echo "poster volume backup verified: $dump ($(wc -c < "$dump") bytes, $files_archive files)"
