"""Write aggregate offsite freshness for node-exporter's textfile collector."""
from datetime import datetime, timezone
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / "backups/metrics"
destination.mkdir(mode=0o755, parents=True, exist_ok=True)
lines = ["# TYPE anicast_offsite_backup_timestamp_seconds gauge"]
for kind in ("db", "posters", "recovery-kit"):
    try:
        stamp = (root / "backups" / kind / "last_offsite_backup").read_text().strip()
        value = int(datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp())
    except (OSError, ValueError):
        value = 0
    lines.append(f'anicast_offsite_backup_timestamp_seconds{{kind="{kind}"}} {value}')
temporary = destination / "backup.prom.tmp"
temporary.write_text("\n".join(lines) + "\n")
temporary.chmod(0o644)
os.replace(temporary, destination / "backup.prom")
