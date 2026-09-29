"""Aggregate stored fixed-state interval coverage; no refitting or label queries."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    package_root = Path(__file__).resolve().parents[1]
    archive_root = package_root.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=archive_root / "data" / "confirmation")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=package_root / "reproducibility" / "confirmation_d_only_manifest.json",
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    if manifest.get("json_count") != 3216:
        raise ValueError(f"unexpected confirmation manifest size: {manifest.get('json_count')}")
    entries = {item["path"].replace("/", "\\"): item for item in manifest["files"]}

    methods = {
        "RAW": "RAW",
        "GLOBAL": "GLOBAL",
        "OOF_ALPHA_1": "LOCAL (alpha=1)",
        "OOF_ALPHA_0.5": "LOCAL (alpha=0.5)",
    }
    levels = [(50, "coverage_50"), (80, "coverage_80"), (90, "coverage_90"), (95, "coverage_95")]
    agg = defaultdict(list)
    records = 0
    eligible_states = 0
    missing_or_invalid = []
    verified_hashes = 0
    for path in sorted(args.runs.glob("*__rank__RAW.json")):
        rel = f"runs\\confirmation\\{path.name}"
        authority = entries.get(rel)
        if authority is None:
            raise ValueError(f"rank-RAW JSON absent from source manifest: {rel}")
        if path.stat().st_size != authority["bytes"] or sha256(path).lower() != authority["sha256"].lower():
            raise ValueError(f"rank-RAW JSON hash/size mismatch: {path}")
        verified_hashes += 1
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        records += 1
        if data.get("status") != "complete" or data.get("rule") != "rank" or data.get("condition") != "RAW":
            missing_or_invalid.append(path.name)
            continue
        state_rows = data.get("fixed_state_calibration", [])
        if len(state_rows) != 24:
            missing_or_invalid.append(path.name)
            continue
        for row in state_rows:
            method = row.get("method")
            if method not in methods:
                continue
            eligible_states += 1
            for nominal, key in levels:
                value = float(row[key])
                if not math.isfinite(value):
                    raise ValueError((path.name, method, key, value))
                agg[(method, nominal)].append(value)

    if records != 320 or verified_hashes != 320 or missing_or_invalid:
        raise ValueError(
            f"expected 320 complete hash-verified rank-RAW files; records={records}, "
            f"hashes={verified_hashes}, invalid={missing_or_invalid[:5]}"
        )
    output = package_root / "tables" / "fixed_state_reliability.csv"
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["method", "display", "nominal_coverage", "mean_observed_coverage", "n_fixed_states"])
        for method, display in methods.items():
            for nominal, _ in levels:
                values = agg[(method, nominal)]
                if len(values) != 1280:
                    raise ValueError(f"expected 1280 values for {method}/{nominal}, got {len(values)}")
                writer.writerow([method, display, nominal / 100, sum(values) / len(values), len(values)])
    report = {
        "status": "pass",
        "source_files": records,
        "hash_verified_source_files": verified_hashes,
        "invalid_files": 0,
        "eligible_fixed_state_method_records": eligible_states,
        "observations_per_curve_point": 1280,
        "output": "tables/fixed_state_reliability.csv",
        "source_directory": str(args.runs),
    }
    audit = package_root / "reproducibility" / "fixed_state_reliability_validation.json"
    audit.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
