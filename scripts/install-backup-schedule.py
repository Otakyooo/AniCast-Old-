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
}
owned = {str(root / "scripts" / name) for name in schedule}
lines = [line for line in current.stdout.splitlines() if not owned.intersection(line.split())]
for name, cron in schedule.items():
    executable = ("python3 " if name.endswith(".py") else "sh ") + str(root / "scripts" / name)
    lines.append(f"{cron} {executable} >> {root}/backups/backup.log 2>&1")
subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)
print("UTC schedule installed: DB 6h, media 24h, recovery kit weekly, freshness every 5m")
