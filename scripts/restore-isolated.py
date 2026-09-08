"""Restore a supplied dump on a recovery host, without production access.

python3 scripts/restore-isolated.py DUMP BACKEND_IMAGE POSTGRES_IMAGE [MEDIA_ARCHIVE]
Images must be preloaded, immutable IDs/digests. No real env or user data is logged.
"""
import hashlib
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import uuid


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True, **kwargs)


def main():
    dump = Path(sys.argv[1]).resolve(strict=True)
    backend, postgres = sys.argv[2:4]
    media_archive = Path(sys.argv[4]).resolve(strict=True) if len(sys.argv) > 4 else None
    for image in (backend, postgres):
        assert re.fullmatch(r"(?:[a-z0-9][a-z0-9._:/-]*@)?sha256:[a-f0-9]{64}", image), "immutable image required"
        docker("image", "inspect", image)
    mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    assert int(mem["MemAvailable"].split()[0]) >= 448 * 1024, "recovery host needs at least 448 MiB available"
    prefix = "anicast-restore-" + uuid.uuid4().hex[:12]
    network, volume, database = prefix + "-net", prefix + "-data", prefix + "-pg"
    app = prefix + "-app"
    media_volume = prefix + "-media"
    password = secrets.token_urlsafe(32)
    read_password = secrets.token_urlsafe(32)
    made = []
    started = time.monotonic()
    # Passwords go through inherited environment, not command arguments or logs.
    env = {**os.environ, "POSTGRES_PASSWORD": password}
    try:
        docker("network", "create", "--internal", network); made.append(("network", network))
        if media_archive:
            docker("volume", "create", "--label", "anicast.restore=" + prefix, media_volume); made.append(("volume", media_volume))
            made.append(("container", prefix + "-extract"))
            result = docker("run", "--rm", "--name", prefix + "-extract", "--network", "none",
                   "--memory", "128m", "--memory-swap", "128m", "--cpus", "0.4",
                   "-v", media_volume + ":/data", "-v", str(media_archive) + ":/archive.tar.gz:ro",
                   "-v", str(Path(__file__).with_name("recovery-media.py").resolve()) + ":/extract.py:ro",
                   backend, "python", "/extract.py", "/archive.tar.gz")
            print(result.stdout.strip())
        docker("volume", "create", "--label", "anicast.restore=" + prefix, volume); made.append(("volume", volume))
        made.append(("container", database))
        docker("run", "-d", "--name", database, "--label", "anicast.restore=" + prefix,
               "--network", network, "--memory", "192m", "--memory-swap", "192m", "--cpus", "0.4",
               "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_USER=drill", "-e", "POSTGRES_DB=recovery",
               "-v", volume + ":/var/lib/postgresql/data", postgres,
               "postgres", "-c", "shared_buffers=16MB", "-c", "work_mem=2MB", "-c", "maintenance_work_mem=32MB", "-c", "max_connections=10", env=env)
        for _ in range(60):
            if subprocess.run(["docker", "exec", database, "pg_isready", "-U", "drill", "-d", "recovery"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("isolated PostgreSQL did not start")
        with dump.open("rb") as source:
            subprocess.run(["docker", "exec", "-i", database, "pg_restore", "-U", "drill", "--exit-on-error", "--single-transaction", "--no-owner", "--no-privileges", "-d", "recovery"], stdin=source, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        sql = f"CREATE ROLE drill_reader LOGIN PASSWORD '{read_password}'; GRANT CONNECT ON DATABASE recovery TO drill_reader; GRANT USAGE ON SCHEMA public TO drill_reader; GRANT SELECT ON ALL TABLES IN SCHEMA public TO drill_reader;"
        docker("exec", "-i", database, "psql", "-U", "drill", "-d", "recovery", "-v", "ON_ERROR_STOP=1", input=sql)
        runtime = {**os.environ, "POSTGRES_PASSWORD": read_password, "DJANGO_SECRET_KEY": secrets.token_urlsafe(48)}
        # No host ports, production volume, real secrets, workers or outbound network.
        made.append(("container", app))
        media_args = ["-v", media_volume + ":/app/media:ro", "-e", "DRILL_MEDIA=1"] if media_archive else []
        result = docker("run", "--rm", "--name", app, "--label", "anicast.restore=" + prefix,
               "--network", network, "--memory", "160m", "--memory-swap", "160m", "--cpus", "0.4",
               "-e", "POSTGRES_PASSWORD", "-e", "DJANGO_SECRET_KEY", "-e", "POSTGRES_USER=drill_reader",
               "-e", "POSTGRES_DB=recovery", "-e", "POSTGRES_HOST=" + database,
               "-e", "DJANGO_DEBUG=1", "-e", "DJANGO_EMAIL_BACKEND=django.core.mail.backends.dummy.EmailBackend",
               "-v", str(Path(__file__).with_name("recovery-smoke.py").resolve()) + ":/app/recovery_smoke.py:ro",
               *media_args, backend, "python", "/app/recovery_smoke.py", env=runtime)
        print(result.stdout.strip())
        with dump.open("rb") as source:
            print("dump_sha256=" + hashlib.file_digest(source, "sha256").hexdigest())
        print("restore_and_smoke_seconds=" + str(round(time.monotonic() - started, 2)))
    except subprocess.CalledProcessError:
        # Raw pg_restore/API exception text can include personal data or secrets.
        raise RuntimeError("isolated recovery step failed; no production state was changed") from None
    finally:
        for kind, name in reversed(made):
            assert name.startswith(prefix + "-")
            command = ["docker", "rm", "-f", "-v", name] if kind == "container" else ["docker", kind, "rm", name]
            result = subprocess.run(command, capture_output=True)
            if result.returncode and kind != "container":
                raise RuntimeError("recovery resource cleanup failed: " + kind)
        print("isolated recovery resources removed")


if __name__ == "__main__":
    main()
