#!/bin/sh
# Hermetic backup failure gates; never calls production Docker, storage or Telegram.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/scripts" "$tmp/infra/mainserver" "$tmp/bin"
cp "$root/scripts/backup-db.sh" "$tmp/scripts/"
printf 'POSTGRES_USER=test\nPOSTGRES_DB=test\n' > "$tmp/infra/mainserver/.env"
cat > "$tmp/bin/docker" <<'EOF'
#!/bin/sh
case "$*" in
  *pg_dump*) python3 -c 'print("x" * 2048)' ;;
  *pg_restore*) cat >/dev/null ;;
  *) exit 1 ;;
esac
EOF
cat > "$tmp/bin/rclone" <<'EOF'
#!/bin/sh
case "$1" in
  listremotes) printf 'gdcrypt:\n' ;;
  copy) exit "${FAIL_UPLOAD:-0}" ;;
  delete) exit 0 ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$tmp/bin/"*
run() { PATH="$tmp/bin:$PATH" BACKUP_NOTIFY=0 RCLONE_BIN="$1" sh "$tmp/scripts/backup-db.sh"; }
if run /missing-rclone; then echo 'missing offsite must fail' >&2; exit 1; fi
test ! -e "$tmp/backups/db/last_offsite_backup"
if FAIL_UPLOAD=1 run "$tmp/bin/rclone"; then echo 'failed upload must fail' >&2; exit 1; fi
test ! -e "$tmp/backups/db/last_offsite_backup"
run "$tmp/bin/rclone"
test -s "$tmp/backups/db/last_offsite_backup"
exec 8>"$tmp/backups/.backup-db.lock"
flock 8
if run "$tmp/bin/rclone"; then echo 'overlapping backup must fail' >&2; exit 1; fi
exec 8>&-
echo 'PASS: missing storage, upload failure, success marker and overlap protection'
