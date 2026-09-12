#!/bin/sh
# Fail on likely-irreversible migrations unless explicitly approved.
# Usage: sh scripts/check-migration-safety.sh [base-ref]
#   MIGRATION_BREAKING_APPROVED="catalog.0021,library.0014" sh scripts/check-migration-safety.sh origin/main
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
base=${1:-origin/main}
approved=${MIGRATION_BREAKING_APPROVED:-}
changed=$(git -C "$root" diff --name-only --diff-filter=AM "$base"...HEAD -- 'backend/*/migrations/*.py' 2>/dev/null || true)
[ -n "$changed" ] || { echo "no new migrations vs $base"; exit 0; }
dangerous=""
for file in $changed; do
    path="$root/$file"
    [ -f "$path" ] || continue
    if grep -Eq 'RemoveField|RemoveModel|DeleteModel|RunSQL[^,]*reverse_sql\s*=\s*None|AlterField.*null\s*=\s*False' "$path"; then
        name=$(basename "$(dirname "$path")").$(basename "$path" .py)
        case ",$approved," in
            *",$name,"*) echo "approved breaking migration: $file" ;;
            *) dangerous="$dangerous $file" ;;
        esac
    fi
done
if [ -n "$dangerous" ]; then
    echo "possibly irreversible migrations require expand/contract or explicit approval:" >&2
    for file in $dangerous; do echo " - $file" >&2; done
    echo "Set MIGRATION_BREAKING_APPROVED=\"<app>.<migration>,...\" with a maintenance/restore plan." >&2
    exit 1
fi
echo "migration safety check passed"
