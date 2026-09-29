from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ALPHAS = (0.25, 0.50, 0.75, 1.00)
ENVS = (("matbench_expt_gap", "iid_record"),
        ("matbench_mp_gap", "iid_record"),
        ("matbench_mp_gap", "chemical_system_ood"),
        ("matbench_log_kvrh", "chemical_system_ood"))
SEEDS = tuple(range(2026092600, 2026092620))
POLICIES = ("rank", "magnitude")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    src, out = args.v2_root.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    v2_protocol = json.loads((src / "V2_PROTOCOL.json").read_text(encoding="utf-8"))
    v2_hash = sha(src / "V2_PROTOCOL.json")
    v2_manifest = pd.read_csv(src / "V2_RUN_MANIFEST.csv")
    if len(v2_manifest) != 640 or v2_manifest.status.ne("complete").any():
        raise ValueError("source V2 run manifest is incomplete")
    original_runner = src / "code" / "run_v2_campaign.py"
    source_files = {
        "v2_protocol_json_sha256": v2_hash,
        "v2_runner_sha256": sha(original_runner),
        "v2_data_manifest_sha256": sha(src / "manifests" / "v2_data_manifest.json"),
        "v2_split_membership_sha256": sha(src / "manifests" / "v2_split_membership.parquet"),
        "v2_dataset_files": {p.name: sha(p) for p in sorted((src / "data_snapshot").glob("*.csv"))},
    }
    raw_rows = v2_manifest[v2_manifest.condition.eq("RAW") & v2_manifest.apply(
        lambda r: (r.task, r.split) in ENVS, axis=1)]
    if len(raw_rows) != 160 or raw_rows.status.ne("complete").any():
        raise ValueError("the 160 matched frozen RAW baselines are not present")
    baseline_path = out / "alpha_raw_baseline_manifest.csv"
    raw_rows[["job_id", "task", "split", "seed", "policy", "result_path", "result_sha256"]].to_csv(baseline_path, index=False)

    protocol = {
        "protocol_id": "MLST_decision_relevance_alpha_sensitivity_v1_20260927",
        "status": "frozen_before_alpha_reruns",
        "analysis_class": "SECONDARY ALPHA-SENSITIVITY ANALYSIS",
        "purpose": "Evaluate whether the qualitative task/policy pattern is sensitive to the fixed LOCAL interpolation exponent; not alpha optimization.",
        "source_v2_protocol_sha256": v2_hash,
        "source_v2_protocol_id": v2_protocol["protocol_id"],
        "source_v2_runner_sha256": source_files["v2_runner_sha256"],
        "alpha_driver_sha256": sha(Path(__file__).with_name("run_alpha_sensitivity.py")),
        "source_data_hashes": source_files,
        "alphas": list(ALPHAS),
        "representative_environments": [{"task": t, "split": s} for t, s in ENVS],
        "policies": list(POLICIES),
        "seeds": list(SEEDS),
        "seed_count": len(SEEDS),
        "local_trajectory_count": len(ALPHAS) * len(ENVS) * len(POLICIES) * len(SEEDS),
        "raw_baseline_count": len(raw_rows),
        "implementation_canary": "One alpha=0.50 magnitude trajectory was run after the initial dry protocol was written to validate the independent runner. It is retained separately under the revision root, excluded from the 640-run main manifest, and the finalized driver hash is frozen in this protocol.",
        "raw_baseline": "Reuse the matching RAW trajectories from the fully verified V2.1 campaign; the RAW rule does not depend on alpha. Verify their hashes from alpha_raw_baseline_manifest.csv before analysis.",
        "alpha_0p5": "Rerun sequentially as an independent sensitivity trajectory and compare against the frozen V2 LOCAL trajectory for exact reproducibility; do not replace either record.",
        "fixed_settings_inherited_from_v2": {
            "data_snapshot": "identical frozen D-drive V2.1 snapshots",
            "split_membership": "identical frozen V2 split file",
            "surrogate": "RandomForestRegressor, 80 trees, min_samples_leaf=2, max_features=1.0, bootstrap, n_jobs=1",
            "oob_residual_ratio": "identical V2.1 implementation",
            "scale_model": "ExtraTreesRegressor, 64 trees, min_samples_leaf=5, max_features=1.0",
            "normalization": "five-fold stable-ID OOF median normalization against 0.67448975",
            "clip": [0.25, 4.0],
            "acquisition": "rank=percentile(mu)+percentile(sigma); magnitude=mu+sigma; ties by stable ID",
            "schedule": "four sequential updates; same initial labels, query budget and deterministic seed derivation",
            "target_tails": [0.005, 0.01, 0.05],
        },
        "sequential_replay_requirement": "Each alpha gets a fresh campaign; never rescore or replay stored alpha=0.5 candidate states as another alpha.",
        "aggregation": "Environment-level and equal-weight average over the four prespecified environments within each of 20 paired V2 seeds; report seed SD, observed range and positive-seed count descriptively; no inferential tests.",
        "calibration_metric": "mean diagnostic-partition MACE over the same four stages; descriptive only.",
        "outputs": ["alpha_sensitivity_run_manifest.csv", "alpha_sensitivity_summary.csv", "alpha_sensitivity.pdf", "supplementary_alpha_table.csv"],
        "frozen_primary_boundary": "No primary confirmation records, estimates, inference, Table 1 values, V2.1 protocol, V2.1 run manifest or V2.1 outputs are modified.",
    }
    (out / "ALPHA_SENSITIVITY_PROTOCOL.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    protocol_hash = sha(out / "ALPHA_SENSITIVITY_PROTOCOL.json")
    rows = []
    for alpha in ALPHAS:
        for task, split in ENVS:
            for policy in POLICIES:
                for seed in SEEDS:
                    job_id = f"ALPHA_{task}_{split}_{seed}_{policy}_a{str(alpha).replace('.', 'p')}"
                    config = {"task": task, "split": split, "seed": seed, "policy": policy,
                              "condition": "LOCAL", "surrogate": "RandomForestRegressor", "alpha": alpha}
                    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    rows.append({"job_id": job_id, "analysis_class": protocol["analysis_class"],
                                 "task": task, "split": split, "seed": seed,
                                 "surrogate": "RandomForestRegressor", "policy": policy,
                                 "alpha": alpha, "condition": "LOCAL", "repeat": 1,
                                 "protocol_sha256": protocol_hash, "source_v2_protocol_sha256": v2_hash,
                                 "config_sha256": config_hash,
                                 "candidate_state_path": f"alpha_candidate_states/{job_id}",
                                 "result_path": f"alpha_results/{job_id}.json",
                                 "status": "planned", "runtime_seconds": "", "result_sha256": "", "error": ""})
    pd.DataFrame(rows).to_csv(out / "alpha_sensitivity_run_manifest.csv", index=False)
    print(json.dumps({"protocol": str(out / "ALPHA_SENSITIVITY_PROTOCOL.json"),
                      "protocol_sha256": protocol_hash, "local_jobs": len(rows),
                      "raw_baselines": len(raw_rows), "alpha_protocol_frozen": True}, indent=2))


if __name__ == "__main__":
    main()
