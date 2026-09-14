"""Encrypt deployment credentials directly to an offline SSH/age recipient.

Run on MainServer or VPS: ROLE REPO_ROOT RECIPIENT_FILE OUTPUT.age
No plaintext archive is written, no credentials or file contents are logged.
The decryption identity must live outside both servers (e.g. the operator's PC).
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time


def main():
    role, root_arg, recipient_arg, output_arg = sys.argv[1:]
    if role not in ("mainserver", "vps"):
        raise SystemExit("role must be mainserver or vps")
    root = Path(root_arg).resolve(strict=True)
    recipient = Path(recipient_arg).resolve(strict=True)
    output = Path(output_arg).resolve()
    if output.exists() or output.suffix != ".age":
        raise SystemExit("choose a new .age output")
    os.umask(0o077)
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_home = Path.home()
    files = {f"infra/{role}/runtime.env": root / f"infra/{role}/.env"}
    files[f"infra/{role}/compose.yml"] = root / f"infra/{role}/compose.yml"
    for name in ("deploy.sh", "rollback.sh", "start-release.sh", "verify-deploy.sh"):
        files["scripts/" + name] = root / "scripts" / name
    if role == "mainserver":
        files.update({
            "recovery/rclone.conf": private_home / ".config/rclone/rclone.conf",
            "recovery/vps-ssh-key": private_home / ".ssh/id_ed25519",
            "recovery/known_hosts": private_home / ".ssh/known_hosts",
            "infra/monitoring/runtime.env": root / "infra/monitoring/.env",
        })
        for p in (root / "infra/monitoring/secrets").iterdir():
            if p.is_file():
                files["infra/monitoring/secrets/" + p.name] = p
        # deploy.sh promotes the live manifest under /var/lib; the old
        # backups/releases path was abandoned on 2026-09-10 and made every
        # kit record a stale release.
        state = Path("/var/lib/anicast/releases/mainserver/current.env")
        for name in ("compose.yml", "prometheus.yml", "alertmanager.yml", "blackbox.yml", "rules/anicast-alerts.yml", "nginx/metrics-proxy.conf"):
            files["infra/monitoring/" + name] = root / "infra/monitoring" / name
    else:
        files["recovery/awg0.conf"] = Path("/etc/amnezia/amneziawg/awg0.conf")
        for name in ("Caddyfile", "firewall.nft"):
            files["infra/vps/" + name] = root / "infra/vps" / name
        state = Path("/var/lib/anicast/releases/vps/current.env")
    files["recovery/current.env"] = state
    values = dict(line.split("=", 1) for line in state.read_text().splitlines() if "=" in line)
    files[f"infra/{role}/release-runtime.env"] = Path(values["ANICAST_ENV_FILE"])
    registry = private_home / ".docker/config.json"
    if registry.is_file():
        files["recovery/registry-config.json"] = registry
    for source in files.values():
        if not source.is_file():
            raise SystemExit("required recovery input is missing")
    # Read once: an OAuth refresh may atomically replace rclone.conf while the
    # kit is being made. Hash exactly the bytes we encrypt.
    contents = {name: path.read_bytes() for name, path in files.items()}
    metadata = {"role": role, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}}
    temporary = output.with_suffix(".age.partial")
    age = os.environ.get("AGE_BIN", str(private_home / ".local/bin/age"))
    try:
        with temporary.open("xb") as destination:
            process = subprocess.Popen([age, "-R", str(recipient)], stdin=subprocess.PIPE, stdout=destination, stderr=subprocess.PIPE)
            try:
                with tarfile.open(fileobj=process.stdin, mode="w|gz") as archive:
                    for name, data in contents.items():
                        info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o600
                        archive.addfile(info, io.BytesIO(data))
                    data = json.dumps(metadata).encode()
                    info = tarfile.TarInfo("recovery/manifest.json"); info.size = len(data); info.mode = 0o600
                    archive.addfile(info, io.BytesIO(data))
                process.stdin.close()
                if process.wait() != 0:
                    raise RuntimeError("recovery kit encryption failed")
            finally:
                if process.poll() is None:
                    process.kill(); process.wait()
        temporary.rename(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Encrypted {role} recovery kit created; {len(files)} private files")


if __name__ == "__main__":
    main()
