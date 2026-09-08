"""Verify an age recovery kit on the operator workstation without extraction."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("archive", type=Path)
parser.add_argument("--identity", required=True, type=Path)
parser.add_argument("--age-bin", default="age")
args = parser.parse_args()
result = subprocess.run([args.age_bin, "-d", "-i", str(args.identity), str(args.archive)], capture_output=True)
if result.returncode:
    raise SystemExit("Cannot decrypt recovery kit; details withheld")
with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:gz") as archive:
    members = archive.getmembers()
    assert all(m.isfile() and not m.name.startswith("/") and ".." not in Path(m.name).parts for m in members)
    metadata = json.load(archive.extractfile("recovery/manifest.json"))
    assert metadata["role"] in ("mainserver", "vps")
    expected = metadata["files"]
    assert len(members) == len(expected) + 1
    for name, digest in expected.items():
        assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest, "recovery checksum mismatch"
print(f"Recovery kit verified: role={metadata['role']}, files={len(expected)}, created={metadata['created_utc']}; no plaintext files extracted")
