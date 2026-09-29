from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a relative-path SHA256SUMS.txt manifest.")
    parser.add_argument("manifest", nargs="?", default="SHA256SUMS.txt")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    manifest = (root / args.manifest).resolve()
    if root not in manifest.parents:
        parser.error("manifest must be inside the current package directory")
    failures = 0
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            print(f"MISSING/INVALID {line_number}: {relative}")
            failures += 1
            continue
        actual = digest(path)
        if actual != expected:
            print(f"MISMATCH {relative}")
            failures += 1
    print(f"checked={sum(1 for x in manifest.read_text(encoding='utf-8').splitlines() if x.strip())} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
