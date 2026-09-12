"""Install Anicast's UTC backup schedule, preserving unrelated crontab entries."""
from pathlib import Path
import os
import subprocess
import time

root = Path(__file__).resolve().parents[1]
assert str(root) == "/home/lama_admin/anicast", "run on canonical MainServer checkout"
assert subprocess.check_output(["date", "+%Z"], text=True).strip() == "UTC", "schedule assumes host UTC"
os.umask(0o077)
current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
assert current.returncode in (0, 1)
saved = root / "backups" / ("crontab-before-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
saved.write_text(current.stdout)
schedule = {
    "backup-db.sh": "15 */6 * * *",
    "backup-posters.sh": "45 3 * * *",
    "backup-recovery-kit.sh": "5 5 * * 0",
    "backup-metrics.py": "*/5 * * * *",
    "restore-db.sh --verify": "30 4 * * 0",
    "prune-docker-cache.sh": "10 5 * * *",
}
owned = {str(root / "scripts" / name.split()[0]) for name in schedule}
lines = [line for line in current.stdout.splitlines() if not owned.intersection(line.split())]
for name, cron in schedule.items():
    base = name.split()[0]
    args = name[len(base):]
    executable = ("python3 " if base.endswith(".py") else "sh ") + str(root / "scripts" / base) + args
    log = root / "backups" / ("restore-verify.log" if base == "restore-db.sh" else "maintenance.log" if base == "prune-docker-cache.sh" else "backup.log")
    lines.append(f"{cron} {executable} >> {log} 2>&1")
subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)
print("UTC schedule installed: DB 6h, media 24h, recovery kit weekly, freshness every 5m, restore verify weekly, prune daily")
