"""Exercise the actual staged rollout with a slow, disposable bulk worker."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


def main():
    source = Path(__file__).resolve().parents[2]
    backend_image, utility_image = sys.argv[1:]
    project = "anicast-rollout-drill-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="anicast-rollout-") as directory:
        root = Path(directory)
        (root / "scripts").mkdir()
        (root / "infra/mainserver").mkdir(parents=True)
        shutil.copyfile(source / "scripts/start-release.sh", root / "scripts/start-release.sh")
        health = {"test": ["CMD", "sh", "-c", "exit 0"], "interval": "1s", "timeout": "1s", "retries": 3}
        services = {}
        for name in ("postgres", "redis", "redis-cache", "redis-control", "celery-worker", "celery-beat", "celery-bulk"):
            delay = 8 if name == "celery-bulk" else 0
            services[name] = {
                "image": utility_image, "mem_limit": "32m", "entrypoint": [],
                "command": ["sh", "-c", f"trap 'sleep {delay}; exit 0' TERM; while :; do sleep 1 & wait $!; done"],
                "labels": {"release": "${RELEASE_SHA}"}, "healthcheck": health,
            }
        probe = "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000', timeout=2).close()"
        services["backend"] = {
            "image": backend_image, "mem_limit": "64m", "entrypoint": [],
            "command": ["python", "-m", "http.server", "8000"],
            "labels": {"release": "${RELEASE_SHA}"},
            "healthcheck": {"test": ["CMD", "python", "-c", probe], "interval": "1s", "timeout": "3s", "retries": 3},
        }
        compose_file = root / "infra/mainserver/compose.yml"
        compose_file.write_text(json.dumps({"services": services}), encoding="utf-8")
        manifest = root / "release.env"
        manifest.write_text("RELEASE_SHA=old\n", encoding="utf-8")
        compose = ["docker", "compose", "--project-name", project, "--env-file", str(manifest), "-f", str(compose_file)]

        def run(args, check=True):
            return subprocess.run(args, check=check, capture_output=True, text=True, timeout=60)

        child = None
        try:
            run(compose + ["up", "-d", "--wait", "--wait-timeout", "30"])
            old_bulk = run(compose + ["ps", "-q", "celery-bulk"]).stdout.strip()
            manifest.write_text("RELEASE_SHA=new\n", encoding="utf-8")
            child = subprocess.Popen(["sh", str(root / "scripts/start-release.sh"), "mainserver", str(manifest)],
                env={**os.environ, "ANICAST_PROJECT_MAINSERVER": project}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            deadline = time.monotonic() + 120
            overlap_probes = 0
            while child.poll() is None:
                if time.monotonic() > deadline:
                    raise AssertionError("Disposable rollout timed out")
                api_id = run(compose + ["ps", "-q", "backend"]).stdout.strip()
                api = run(["docker", "inspect", api_id], check=False) if api_id else None
                if api and api.returncode == 0:
                    state = json.loads(api.stdout)[0]
                    if state["Config"]["Labels"]["release"] == "new" and state["State"].get("Health", {}).get("Status") == "healthy":
                        old = run(["docker", "inspect", old_bulk], check=False)
                        if old.returncode == 0 and json.loads(old.stdout)[0]["State"]["Running"]:
                            run(["docker", "exec", api_id, "python", "-c", probe])
                            overlap_probes += 1
                time.sleep(1)
            stdout, stderr = child.communicate(timeout=10)
            assert child.returncode == 0, stdout + stderr
            assert overlap_probes >= 3, f"Only {overlap_probes} API probes while old bulk was draining"
            print(f"Disposable rollout passed: {overlap_probes} successful new-API probes before old bulk exited")
        finally:
            try:
                if child and child.poll() is None:
                    child.terminate()
                    child.communicate(timeout=10)
            finally:
                run(compose + ["down", "--timeout", "10", "--volumes", "--remove-orphans"])


if __name__ == "__main__":
    main()
