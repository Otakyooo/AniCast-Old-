"""Bounded streaming extraction into an empty disposable media volume."""
import json
from pathlib import Path
import shutil
import sys
import tarfile

root = Path("/data").resolve()
files = total = 0
with tarfile.open(sys.argv[1], "r|gz") as archive:
    for member in archive:
        target = (root / member.name).resolve()
        assert target == root or root in target.parents, "unsafe archive path"
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        assert member.isfile(), "links and special objects are not accepted"
        files += 1
        total += member.size
        assert files <= 100000 and total <= 2 * 1024**3 and 0 < member.size <= 16 * 1024**2, "media archive exceeds drill limits"
        source = archive.extractfile(member)
        header = source.read(12)
        assert header.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")) or (header[:4] == b"RIFF" and header[8:12] == b"WEBP"), "unrecognized media object"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(header)
            shutil.copyfileobj(source, output, length=64 * 1024)
        assert target.stat().st_size == member.size, "truncated media object"
assert files > 0
print(json.dumps({"restored_media_files": files, "restored_media_bytes": total}))
