"""Generate repository-relative SHA-256 entries for Git-tracked release files."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SHA256SUMS.txt"


def main() -> None:
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    paths = sorted({p for p in raw.decode("utf-8").split("\0") if p and p != "SHA256SUMS.txt"})
    lines = []
    for relative in paths:
        path = ROOT / Path(relative)
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {Path(relative).as_posix()}\n")
    MANIFEST.write_text("".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {len(lines)} repository-relative hashes to {MANIFEST.name}")


if __name__ == "__main__":
    main()
