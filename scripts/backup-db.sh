#!/bin/sh
set -eu
umask 077

# AniCast PostgreSQL backup: verified local dump with retention and an
# encrypted offsite copy on Google Drive (rclone crypt remote gdcrypt:).

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
mkdir -p "$root/backups"
exec 9>"$root/backups/.backup-db.lock"
flock -n 9 || { echo "another db backup is active" >&2; exit 75; }
backup_dir=${BACKUP_DIR:-$root/backups/db}
rclone_bin=${RCLONE_BIN:-$HOME/.local/bin/rclone}
rclone_remote=${RCLONE_REMOTE:-gdcrypt:db}
pg_container=${PG_CONTAINER:-mainserver-postgres-1}
retention_days=${RETENTION_DAYS:-14}
weekly_keep_days=${WEEKLY_KEEP_DAYS:-60}
offsite_min_age_days=${OFFSITE_MIN_AGE_DAYS:-90}

pg_user=$(sed -n 's/^POSTGRES_USER=//p' "$root/infra/mainserver/.env")
pg_db=$(sed -n 's/^POSTGRES_DB=//p' "$root/infra/mainserver/.env")
[ -n "$pg_user" ] && [ -n "$pg_db" ] || {
    echo "POSTGRES_USER/POSTGRES_DB missing in infra/mainserver/.env" >&2
    exit 2
}

ops_env=$root/infra/monitoring/.env
# api.telegram.org is unreachable from this host, so failure alerts go through the
# relay inside the tunnel. Calling Telegram directly meant a failing backup
# reported itself only to stderr, which nobody reads on a cron run — the alert was
# silently discarded exactly when it mattered.
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
    curl -fsS -m 20 "${telegram_api%/}/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat_id}" \
        --data-urlencode "text=${message}" >/dev/null 2>&1 || true
}

failure_reported=0
backup_exit() {
    code=$?
    if [ "$code" -ne 0 ] && [ "$failure_reported" = 0 ]; then
        alert "Anicast db backup failed; inspect the private backup log"
    fi
    exit "$code"
}
trap backup_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
dump=$backup_dir/anicast-$timestamp.dump
tmp_dump=$dump.tmp.$$

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

if ! docker exec "$pg_container" pg_dump -U "$pg_user" -d "$pg_db" -Fc \
        > "$tmp_dump" 2> "$backup_dir/.pg_dump.err"; then
    rm -f "$tmp_dump" "$backup_dir/.pg_dump.err"
    alert "AniCast backup FAILED: pg_dump error (details withheld)"
    exit 1
fi
rm -f "$backup_dir/.pg_dump.err"
mv "$tmp_dump" "$dump"
chmod 600 "$dump"

size=$(wc -c < "$dump")
if [ "$size" -lt 1024 ]; then
    rm -f "$dump"
    alert "AniCast backup FAILED: dump suspiciously small ($size bytes)"
    exit 1
fi

# Check the archive header/TOC; only a restore drill validates its data blocks.
if ! docker exec -i "$pg_container" pg_restore --list < "$dump" \
        >/dev/null 2> "$backup_dir/.verify.err"; then
    rm -f "$dump" "$backup_dir/.verify.err"
    alert "AniCast backup FAILED: dump verification error (details withheld)"
    exit 1
fi
rm -f "$backup_dir/.verify.err"

# Retention: keep all dumps from the recent window, keep older Sunday
# dumps for a longer disaster-recovery horizon. Manual predeploy-* dumps
# in backups/ are never touched.
now=$(date +%s)
for old in "$backup_dir"/anicast-*.dump; do
    [ -f "$old" ] || continue
    age=$(( (now - $(stat -c %Y "$old")) / 86400 ))
    if [ "$age" -le "$retention_days" ]; then continue; fi
    weekday=$(date -u -r "$old" +%u)
    if [ "$weekday" = "7" ] && [ "$age" -le "$weekly_keep_days" ]; then continue; fi
    rm -f "$old" "$old.sha256"
done

sha256sum "$dump" > "$dump.sha256"

if [ -x "$rclone_bin" ] && "$rclone_bin" listremotes 2>/dev/null | grep -q '^gdcrypt:$'; then
    if ! "$rclone_bin" copy --quiet "$dump" "$rclone_remote"; then
        alert "AniCast backup WARNING: local dump succeeded but Google Drive upload failed for $dump"
        exit 1
    fi
    "$rclone_bin" copy --quiet "$dump.sha256" "$rclone_remote"
    "$rclone_bin" delete --quiet --min-age "${offsite_min_age_days}d" "$rclone_remote"
else
    [ "${ALLOW_LOCAL_BACKUP:-0}" = 1 ] || {
        alert "Anicast backup FAILED: offsite remote unavailable"
        exit 1
    }
    echo "explicit local-only backup; no offsite success marker" >&2
fi

printf '%s %s\n' "$timestamp" "$dump" > "$backup_dir/last_backup"
if [ "${ALLOW_LOCAL_BACKUP:-0}" != 1 ]; then
    printf '%s\n' "$timestamp" > "$backup_dir/last_offsite_backup"
fi

echo "backup ok: $dump ($size bytes)"
