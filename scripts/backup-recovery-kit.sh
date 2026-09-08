#!/bin/sh
set -eu
umask 077
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
out="$root/backups/recovery-kit"
mkdir -p "$out"
exec 9>"$out/.lock"
flock -n 9 || exit 75
recipient="$HOME/.config/anicast/recovery-recipient.txt"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
python3 "$root/scripts/backup-recovery-kit.py" mainserver "$root" "$recipient" "$out/mainserver-$stamp.age"
# Only ciphertext crosses hosts. Each host retains the public recipient, never
# the offline decryption identity. No plaintext archive is created.
ssh -n -o BatchMode=yes -o ConnectTimeout=15 root@10.78.0.1 \
    "python3 /opt/anicast/scripts/backup-recovery-kit.py vps /opt/anicast /root/.config/anicast/recovery-recipient.txt /root/anicast-recovery-kit/vps-$stamp.age"
scp -q -o BatchMode=yes "root@10.78.0.1:/root/anicast-recovery-kit/vps-$stamp.age" "$out/"
"$HOME/.local/bin/rclone" copy --quiet "$out/mainserver-$stamp.age" gdcrypt:recovery
"$HOME/.local/bin/rclone" copy --quiet "$out/vps-$stamp.age" gdcrypt:recovery
"$HOME/.local/bin/rclone" delete --quiet --min-age 90d gdcrypt:recovery
printf '%s\n' "$stamp" > "$out/last_offsite_backup"
echo 'Encrypted recovery kits uploaded'
