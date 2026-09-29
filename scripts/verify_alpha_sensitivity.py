from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


COMPARE = ["material_id", "true_y_retrospective", "predicted_mu", "raw_sigma", "local_scale",
           "predicted_value_rank", "uncertainty_rank_raw", "acquisition_score", "acquisition_rank",
           "selected_flag", "query_order", "counterfactual_raw_rank", "counterfactual_raw_selected",
           "counterfactual_local_rank", "counterfactual_local_selected", "top_tail_0p5", "top_tail_1", "top_tail_5"]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify alpha-sensitivity manifests, Parquet states, and the alpha=0.50 replay.")
    ap.add_argument("--v2-root", type=Path, required=True)
    ap.add_argument("--alpha-root", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args()
    v2, root = a.v2_root.resolve(), a.alpha_root.resolve()
    protocol_path = root / "ALPHA_SENSITIVITY_PROTOCOL.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_hash = sha(protocol_path)
    manifest = pd.read_csv(root / "alpha_sensitivity_run_manifest.csv", dtype={"status": "string", "result_sha256": "string"})
    if len(manifest) != 640 or manifest.job_id.duplicated().any() or manifest.status.ne("complete").any():
        raise ValueError("alpha manifest is not a complete, unique 640-job campaign")
    if manifest.protocol_sha256.ne(protocol_hash).any():
        raise ValueError("alpha run rows do not use the frozen protocol hash")
    if sha(root.parent / "scripts" / "run_alpha_sensitivity.py") != protocol["alpha_driver_sha256"]:
        raise ValueError("alpha driver changed after protocol freeze")

    v2_manifest = pd.read_csv(v2 / "V2_RUN_MANIFEST.csv")
    if len(v2_manifest) != 640 or v2_manifest.status.ne("complete").any():
        raise ValueError("V2 baseline manifest is incomplete")
    v2_lookup = {(r.task, r.split, int(r.seed), r.policy, r.condition): r for r in v2_manifest.itertuples(index=False)}
    exact_replays, states, replay_jobs = 0, 0, 0
    local_state_rows = []
    for r in manifest.itertuples(index=False):
        result_path = root / r.result_path
        if sha(result_path) != r.result_sha256:
            raise ValueError(f"result hash mismatch: {r.job_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("alpha") != float(r.alpha) or result.get("analysis_class") != "SECONDARY ALPHA-SENSITIVITY ANALYSIS":
            raise ValueError(f"result metadata mismatch: {r.job_id}")
        alpha_col = f"corrected_sigma_alpha_{str(float(r.alpha)).replace('.', 'p')}"
        state_paths = result.get("candidate_state_files", [])
        if len(state_paths) != 4:
            raise ValueError(f"wrong number of stage files: {r.job_id}")
        v2r = v2_lookup[(r.task, r.split, int(r.seed), r.policy, "LOCAL")] if float(r.alpha) == 0.5 else None
        for stage, item in enumerate(state_paths):
            p = root / item["path"]
            if not p.is_file() or sha(p) != item["sha256"]:
                raise ValueError(f"candidate-state hash mismatch: {r.job_id}, stage {stage}")
            state = pd.read_parquet(p)
            if alpha_col not in state or state.stage.nunique() != 1 or int(state.stage.iloc[0]) != stage:
                raise ValueError(f"state schema/stage mismatch: {r.job_id}, stage {stage}")
            if state.material_id.duplicated().any() or state.target_labels_used_for_acquisition.astype(bool).any():
                raise ValueError(f"candidate identity or label-isolation check failed: {r.job_id}, stage {stage}")
            if not np.isfinite(state[["predicted_mu", "raw_sigma", "local_scale", alpha_col]].to_numpy(float)).all():
                raise ValueError(f"non-finite candidate values: {r.job_id}, stage {stage}")
            if not np.array_equal(state.selected_flag.to_numpy(bool), state.query_order.gt(0).to_numpy(bool)):
                raise ValueError(f"selected flag does not match query order: {r.job_id}, stage {stage}")
            local_state_rows.append(len(state))
            states += 1
            if v2r is not None:
                ref = pd.read_parquet(v2 / v2r.candidate_state_path / f"stage_{stage}.parquet")
                checks = all(np.array_equal(state[c].to_numpy(), ref[c].to_numpy()) for c in COMPARE)
                checks &= np.array_equal(state[alpha_col].to_numpy(), ref["corrected_sigma_alpha_0p5"].to_numpy())
                checks &= np.array_equal(state.counterfactual_raw_score.to_numpy(), ref.counterfactual_raw_score.to_numpy())
                checks &= np.array_equal(state.counterfactual_local_score.to_numpy(), ref.counterfactual_local_score.to_numpy())
                if not checks:
                    raise ValueError(f"alpha=0.50 replay stage differs from frozen V2: {r.job_id}, stage {stage}")
                exact_replays += 1
        if v2r is not None:
            ref_result = json.loads((v2 / v2r.result_path).read_text(encoding="utf-8"))
            if result["queried_ids_sha256_in_order"] != ref_result["queried_ids_sha256_in_order"]:
                raise ValueError(f"alpha=0.50 query trajectory differs from frozen V2: {r.job_id}")
            replay_jobs += 1

    raw_baselines = pd.read_csv(root / "alpha_raw_baseline_manifest.csv")
    if len(raw_baselines) != 160:
        raise ValueError("expected 160 RAW baseline records")
    raw_verified = 0
    for r in raw_baselines.itertuples(index=False):
        f = v2 / r.result_path
        if not f.is_file() or sha(f) != r.result_sha256:
            raise ValueError(f"RAW baseline hash mismatch: {r.job_id}")
        raw_verified += 1
    report = {"status": "PASS", "protocol_sha256": protocol_hash,
              "manifest_rows": len(manifest), "complete_runs": int(manifest.status.eq("complete").sum()),
              "candidate_state_files_verified": states, "candidate_state_rows": int(sum(local_state_rows)),
              "raw_baselines_hash_verified": raw_verified,
              "alpha_0p50_replay_jobs": replay_jobs, "alpha_0p50_exact_stages": exact_replays,
              "target_labels_used_for_acquisition": False,
              "interpretation": "secondary robustness only; seed and environment summaries are descriptive"}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
