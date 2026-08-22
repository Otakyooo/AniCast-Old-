#!/bin/sh
set -eu

# AniCast PostgreSQL restore.
#   restore-db.sh --verify [dump]   safe check: restore into a scratch database, then drop it
#   restore-db.sh --force [dump]    destructive: replace the production database (stops app containers)
#
# The dump defaults to the newest backups/db/anicast-*.dump. Dumps use the
# pg_dump custom format; pg_restore runs inside the postgres container.

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
backup_dir=${BACKUP_DIR:-$root/backups/db}
pg_container=${PG_CONTAINER:-mainserver-postgres-1}
compose_dir=$root/infra/mainserver
scratch_db=${SCRATCH_DB:-anicast_restore_test}
backend_container=${BACKEND_CONTAINER:-mainserver-backend-1}

mode=${1:-}
case "$mode" in
    --verify|--force) ;;
    *) echo "usage: restore-db.sh --verify|--force [dump]" >&2; exit 2 ;;
esac

if [ $# -ge 2 ]; then
    dump=$(realpath "$2")
else
    dump=$(ls -1t "$backup_dir"/anicast-*.dump 2>/dev/null | head -n 1 || true)
    [ -n "$dump" ] || { echo "no dump found in $backup_dir" >&2; exit 2; }
    dump=$(realpath "$dump")
fi
[ -f "$dump" ] || { echo "dump not found: $dump" >&2; exit 2; }

pg_user=$(sed -n 's/^POSTGRES_USER=//p' "$root/infra/mainserver/.env")
pg_db=$(sed -n 's/^POSTGRES_DB=//p' "$root/infra/mainserver/.env")
[ -n "$pg_user" ] && [ -n "$pg_db" ] || {
    echo "POSTGRES_USER/POSTGRES_DB missing in infra/mainserver/.env" >&2
    exit 2
}

echo "dump: $dump ($(wc -c < "$dump") bytes, created $(date -u -r "$dump" +%Y-%m-%dT%H:%M:%SZ))"

if [ "$mode" = "--verify" ]; then
    docker exec "$pg_container" dropdb -U "$pg_user" --if-exists "$scratch_db"
    docker exec "$pg_container" createdb -U "$pg_user" "$scratch_db"
    if ! docker exec -i "$pg_container" pg_restore -U "$pg_user" \
            --no-owner --no-privileges -d "$scratch_db" < "$dump"; then
        docker exec "$pg_container" dropdb -U "$pg_user" --if-exists "$scratch_db"
        echo "restore verification FAILED: pg_restore reported errors" >&2
        exit 1
    fi
    restored_tables=$(docker exec "$pg_container" psql -U "$pg_user" -d "$scratch_db" -tAc \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
    users=$(docker exec "$pg_container" psql -U "$pg_user" -d "$scratch_db" -tAc \
        "SELECT count(*) FROM accounts_user" 2>/dev/null || echo '?')
    titles=$(docker exec "$pg_container" psql -U "$pg_user" -d "$scratch_db" -tAc \
        "SELECT count(*) FROM catalog_title" 2>/dev/null || echo '?')
    docker exec "$pg_container" dropdb -U "$pg_user" --if-exists "$scratch_db"
    echo "verify ok: $restored_tables tables, accounts_user=$users, catalog_title=$titles (scratch database dropped)"
    exit 0
fi

printf 'This REPLACES production database %s from the dump.\n' "$pg_db"
printf 'App containers (backend, celery) will be stopped during the restore.\n'
printf 'Type the database name to continue: '
read -r reply
[ "$reply" = "$pg_db" ] || { echo "aborted" >&2; exit 1; }

( cd "$compose_dir" && docker compose stop backend celery-worker celery-beat )
docker exec "$pg_container" dropdb -U "$pg_user" --if-exists "$pg_db"
docker exec "$pg_container" createdb -U "$pg_user" "$pg_db"
docker exec -i "$pg_container" pg_restore -U "$pg_user" \
    --no-owner --no-privileges -d "$pg_db" < "$dump"
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
echo "restore complete: $pg_db recovered from $dump; backend is healthy"
