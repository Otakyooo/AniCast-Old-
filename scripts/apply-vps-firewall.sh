#!/bin/sh
# Atomically replace only the Anicast table. Requires root on the public VPS.
set -eu
config=${1:-/etc/anicast/firewall.nft}
[ "$(id -u)" = 0 ] || { echo "root is required" >&2; exit 1; }
transaction=$(mktemp)
trap 'rm -f "$transaction"' EXIT INT TERM
if nft list table inet anicast_edge >/dev/null 2>&1; then
    printf 'delete table inet anicast_edge\n' > "$transaction"
fi
cat "$config" >> "$transaction"
nft --check -f "$transaction"
nft -f "$transaction"
