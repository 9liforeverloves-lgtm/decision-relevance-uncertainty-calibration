"""Read-only verification of the frozen primary contrasts from saved JSONs.

Recomputes the existing 40 paired-seed analysis without refitting models and
writes only new audit outputs in this MLST revision copy. It never changes the
frozen experiment records or authority table.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np


CONTRASTS = (
    ("rank", "LOCAL", "RAW"),
    ("rank", "LOCAL", "PERMUTED"),
    ("rank", "LOCAL", "MATCHED"),
    ("magnitude", "LOCAL", "RAW"),
    ("magnitude", "LOCAL", "PERMUTED"),
    ("magnitude", "LOCAL", "MATCHED"),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bootstrap_ci(values: np.ndarray, draws: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(draws, len(values)))
    means = values[indices].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def signflip_pvalue(values: np.ndarray, draws: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    observed = abs(float(values.mean()))
    signs = rng.choice(np.array([-1.0, 1.0]), size=(draws, len(values)))
    null = np.abs((signs * values).mean(axis=1))
    return float((1 + np.count_nonzero(null >= observed)) / (draws + 1))


def holm(pvalues: list[float]) -> list[float]:
    order = np.argsort(pvalues)
    adjusted = np.empty(len(pvalues), float)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[index]))
        adjusted[index] = running
    return adjusted.tolist()


def expected_cases(seed: int) -> set[tuple[str, str]]:
    pairs = {("rank", condition) for condition in ("RAW", "LEGACY_LOCAL", "LOCAL", "PERMUTED", "MATCHED")}
    pairs |= {("magnitude", condition) for condition in ("RAW", "GLOBAL", "LOCAL", "PERMUTED", "MATCHED")}
    if seed in (926500, 926501):
        pairs.add(("rank", "GLOBAL"))
    return pairs


def record_name(task: str, split: str, seed: int, rule: str, condition: str) -> str:
    return f"{task}__{split}__{seed}__{rule}__{condition}.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runs",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "confirmation",
        help="read-only directory containing the frozen confirmation JSONs",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with (root / "reproducibility" / "confirmation_d_only_manifest.json").open(encoding="utf-8") as f:
        manifest = json.load(f)
    with (root / "reproducibility" / "experiment_plan.json").open(encoding="utf-8") as f:
        plan = json.load(f)
    with (root / "reproducibility" / "confirmation_freeze.json").open(encoding="utf-8") as f:
        freeze = json.load(f)

    source_root = args.runs.parent.parent
    code_authorities = {
        "core.py": source_root / "core.py",
        "experiment_plan.json": source_root / "experiment_plan.json",
        "confirmation_freeze.json": source_root / "confirmation_freeze.json",
    }
    authority_checks = {}
    for name, path in code_authorities.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing source authority: {path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = manifest["code"][name]
        authority_checks[name] = {"actual_sha256": actual, "expected_sha256": expected, "match": actual == expected}
        if actual != expected:
            raise ValueError(f"source authority hash mismatch: {name}")

    signature = {
        "core": manifest["code"]["core.py"],
        "plan": manifest["code"]["experiment_plan.json"],
        "alpha": freeze["selected_alpha"],
    }
    file_manifest = {item["path"].replace("/", "\\"): item for item in manifest["files"]}
    tasks = list(plan["tasks"])
    splits = list(plan["splits"])
    seeds = range(plan["confirmation_seeds"]["start"], plan["confirmation_seeds"]["end"] + 1)
    expected_keys = {
        (task, split, seed, rule, condition)
        for seed in seeds
        for task in tasks
        for split in splits
        for rule, condition in expected_cases(seed)
    }
    actual_paths = sorted(args.runs.glob("*.json"))
    if len(actual_paths) != manifest["json_count"] or len(expected_keys) != manifest["json_count"]:
        raise ValueError(f"confirmation count mismatch: files={len(actual_paths)}, expected={len(expected_keys)}, manifest={manifest['json_count']}")

    index: dict[tuple[str, str, int, str, str], dict[str, float]] = {}
    invalid: list[str] = []
    hash_verified = 0
    total_bytes = 0
    for path in actual_paths:
        rel = f"runs\\confirmation\\{path.name}"
        expected_file = file_manifest.get(rel)
        if expected_file is None:
            invalid.append(f"unlisted file: {path.name}")
            continue
        raw = path.read_bytes()
        total_bytes += len(raw)
        if len(raw) != expected_file["bytes"] or sha256_bytes(raw) != expected_file["sha256"]:
            invalid.append(f"hash/size mismatch: {path.name}")
            continue
        hash_verified += 1
        try:
            record = json.loads(raw)
            key = (record["task"], record["split"], int(record["seed"]), record["rule"], record["condition"])
            if key not in expected_keys or key in index:
                invalid.append(f"unexpected/duplicate key: {key}")
                continue
            if record.get("signature") != signature or record.get("status") != "complete" or record.get("cohort") != "confirmation":
                invalid.append(f"signature/status/cohort mismatch: {path.name}")
                continue
            for metric in ("L4_query", "L1", "final_recall", "runtime_seconds"):
                if metric not in record or not math.isfinite(float(record[metric])):
                    raise ValueError(f"missing or non-finite {metric}")
            selected = record.get("selected_ids")
            if not isinstance(selected, list) or len(selected) != int(record["B"]) or len(set(selected)) != len(selected):
                raise ValueError("selected trajectory length/uniqueness mismatch")
            if len(record.get("states", [])) != 4:
                raise ValueError("unexpected sequential stage count")
            index[key] = {"L4_query": float(record["L4_query"])}
        except Exception as exc:
            invalid.append(f"invalid record {path.name}: {exc}")

    missing = sorted(expected_keys - index.keys())
    if invalid or missing or hash_verified != manifest["json_count"] or total_bytes != manifest["total_bytes"]:
        raise ValueError(json.dumps({"invalid_count": len(invalid), "missing_count": len(missing), "hash_verified": hash_verified, "bytes": total_bytes}, indent=2))

    effects = []
    for rule, left, right in CONTRASTS:
        seed_delta = []
        for seed in range(926500, 926540):
            left_values = [index[(task, split, seed, rule, left)]["L4_query"] for task in tasks for split in splits]
            right_values = [index[(task, split, seed, rule, right)]["L4_query"] for task in tasks for split in splits]
            seed_delta.append(float(np.mean(left_values) - np.mean(right_values)))
        values = np.asarray(seed_delta, dtype=float)
        ci = bootstrap_ci(values, 10000, 926900)
        pvalue = signflip_pvalue(values, 20000, 926901)
        effects.append({
            "rule": rule,
            "left": left,
            "right": right,
            "n_seed": len(values),
            "left_seed_mean": float(np.mean([index[(task, split, seed, rule, left)]["L4_query"] for seed in range(926500, 926540) for task in tasks for split in splits])),
            "right_seed_mean": float(np.mean([index[(task, split, seed, rule, right)]["L4_query"] for seed in range(926500, 926540) for task in tasks for split in splits])),
            "mean_delta": float(values.mean()),
            "median_delta": float(np.median(values)),
            "sd_delta": float(values.std(ddof=1)),
            "ci95_low": ci[0],
            "ci95_high": ci[1],
            "signflip_p_two_sided": pvalue,
            "positive_seed_fraction": float(np.mean(values > 0)),
            "practical_threshold": 0.005,
        })
    adjusted = holm([row["signflip_p_two_sided"] for row in effects])
    for row, q in zip(effects, adjusted):
        row["holm_q_two_sided"] = q
        row["matches_frozen_authority"] = False

    authority_path = root / "tables" / "primary_effects.csv"
    with authority_path.open(newline="", encoding="utf-8-sig") as f:
        authority = list(csv.DictReader(f))
    auth = {(row["rule"], row["left"], row["right"]): row for row in authority}
    fields = ("left_seed_mean", "right_seed_mean", "mean_delta", "median_delta", "sd_delta", "ci95_low", "ci95_high", "signflip_p_two_sided", "holm_q_two_sided", "positive_seed_fraction")
    mismatches = []
    for effect in effects:
        frozen = auth[(effect["rule"], effect["left"], effect["right"])]
        effect["matches_frozen_authority"] = all(
            math.isclose(float(effect[field]), float(frozen[{
                "ci95_low": "ci95_low", "ci95_high": "ci95_high",
            }.get(field, field)]), rel_tol=1e-11, abs_tol=1e-12)
            for field in fields
        )
        if not effect["matches_frozen_authority"]:
            mismatches.append({"contrast": [effect["rule"], effect["left"], effect["right"]], "recomputed": effect, "frozen": frozen})

    # Preserve the same paired-seed estimand used above as a plot-ready table.
    # Each point averages the eight fixed task--split environments within seed.
    seed_blocks = []
    for rule, left, right in CONTRASTS:
        for seed in range(926500, 926540):
            left_values = [index[(task, split, seed, rule, left)]["L4_query"] for task in tasks for split in splits]
            right_values = [index[(task, split, seed, rule, right)]["L4_query"] for task in tasks for split in splits]
            seed_blocks.append({
                "rule": rule,
                "contrast": f"{left} - {right}",
                "seed": seed,
                "n_environments": len(tasks) * len(splits),
                "left_mean": float(np.mean(left_values)),
                "right_mean": float(np.mean(right_values)),
                "delta_L4_query": float(np.mean(left_values) - np.mean(right_values)),
            })

    audit = {
        "status": "pass" if not mismatches else "mismatch",
        "analysis": "read-only recomputation of the frozen primary analysis from saved run JSONs; no model refit",
        "source_run_directory": str(args.runs),
        "manifest_json_count": manifest["json_count"],
        "hash_verified_json_count": hash_verified,
        "validated_total_bytes": total_bytes,
        "source_code_hash_checks": authority_checks,
        "missing_records": len(missing),
        "invalid_records": len(invalid),
        "primary_table": str(authority_path),
        "all_six_match_frozen_table": not mismatches,
        "seed_level_plot_data": str(root / "tables" / "primary_seed_blocks.csv"),
        "effects": effects,
        "mismatch_details": mismatches,
    }
    out_json = root / "reproducibility" / "primary_reproduction_check.json"
    out_csv = root / "tables" / "primary_reproduction_check.csv"
    out_json.write_text(json.dumps(audit, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(effects[0]))
        writer.writeheader()
        writer.writerows(effects)
    seed_csv = root / "tables" / "primary_seed_blocks.csv"
    with seed_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(seed_blocks[0]))
        writer.writeheader()
        writer.writerows(seed_blocks)
    print(json.dumps({"status": audit["status"], "hash_verified_json_count": hash_verified, "missing": len(missing), "invalid": len(invalid), "all_six_match_frozen_table": audit["all_six_match_frozen_table"], "effects": effects}, indent=2))
    if mismatches:
        raise SystemExit("Recomputed primary results do not match the frozen authority table.")


if __name__ == "__main__":
    main()
