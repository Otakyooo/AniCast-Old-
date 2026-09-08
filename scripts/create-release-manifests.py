"""Generate secret-free artifacts; bind ANICAST_ENV_FILE on the target host."""
import json
import os
from pathlib import Path
import re
import sys


def manifests(backend_digest, frontend_digest, revision):
    for digest in (backend_digest, frontend_digest):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise ValueError("expected one sha256 prefix and a 64-character digest")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("expected a full commit SHA")
    return {
        "mainserver": {"BACKEND_IMAGE": "ghcr.io/otakyooo/anicast-backend@" + backend_digest, "RELEASE_SHA": revision},
        "vps": {"FRONTEND_IMAGE": "ghcr.io/otakyooo/anicast-frontend@" + frontend_digest, "RELEASE_SHA": revision},
    }


if __name__ == "__main__":
    result = manifests(os.environ["BACKEND_DIGEST"], os.environ["FRONTEND_DIGEST"], os.environ["RELEASE_SHA"])
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    for stack, values in result.items():
        (destination / f"{stack}.env").write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    (destination / "release.json").write_text(json.dumps(result, indent=2) + "\n")
