from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


Z = {50: 0.67448975, 80: 1.28155157, 90: 1.64485363, 95: 1.95996398}
COLS = ["task", "split", "seed", "policy", "condition", "stage", "true_y_retrospective",
        "predicted_mu", "raw_sigma", "corrected_sigma_alpha_0p5", "target_labels_used_for_acquisition"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Exploratory, retrospective V2 target-candidate uncertainty/error diagnostics.")
    ap.add_argument("--v2-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    root, out = a.v2_root.resolve(), a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(root / "V2_RUN_MANIFEST.csv")
    if len(manifest) != 640 or manifest.status.ne("complete").any() or manifest.job_id.duplicated().any():
        raise ValueError("V2 campaign manifest is not complete and unique")
    records = []
    for r in manifest.itertuples(index=False):
        state_dir = root / r.candidate_state_path
        for stage in range(4):
            frame = pd.read_parquet(state_dir / f"stage_{stage}.parquet", columns=COLS)
            if frame.target_labels_used_for_acquisition.astype(bool).any():
                raise ValueError(f"retrospective-label isolation flag failed in {r.job_id} stage {stage}")
            err = np.abs(frame.true_y_retrospective.to_numpy(float) - frame.predicted_mu.to_numpy(float))
            raw = np.maximum(frame.raw_sigma.to_numpy(float), 1e-8)
            local = np.maximum(frame.corrected_sigma_alpha_0p5.to_numpy(float), 1e-8)
            for method, sigma in (("RAW", raw), ("LOCAL_alpha0.5", local)):
                cover = {level: float(np.mean(err <= z * sigma)) for level, z in Z.items()}
                rec = {"analysis_class": "EXPLORATORY DIAGNOSTIC ANALYSIS",
                       "task": r.task, "split": r.split, "seed": int(r.seed),
                       "policy": r.policy, "condition": r.condition, "stage": stage,
                       "diagnostic_method": method, "candidate_n": len(frame),
                       "spearman_abs_error_vs_sigma": float(spearmanr(err, sigma).statistic),
                       "mean_sigma": float(sigma.mean()),
                       "mean_abs_standardized_residual": float(np.mean(err / sigma)),
                       "median_abs_standardized_residual": float(np.median(err / sigma)),
                       "q90_abs_standardized_residual": float(np.quantile(err / sigma, 0.90)),
                       **{f"coverage_{level}": value for level, value in cover.items()},
                       "mace": float(np.mean([abs(cover[p] - p / 100) for p in Z]))}
                records.append(rec)
    stage = pd.DataFrame(records)
    stage.to_csv(out / "v2_candidate_calibration_stage.csv", index=False)
    grouped = (stage.groupby(["task", "split", "policy", "condition", "diagnostic_method"], as_index=False)
               .agg(n_seeds=("seed", "nunique"), n_seed_stage_records=("stage", "size"),
                    **{col: (col, "mean") for col in ["spearman_abs_error_vs_sigma", "mean_sigma",
                       "mean_abs_standardized_residual", "median_abs_standardized_residual",
                       "q90_abs_standardized_residual", "coverage_50", "coverage_80", "coverage_90",
                       "coverage_95", "mace"]}))
    grouped.to_csv(out / "v2_candidate_calibration_environment.csv", index=False)
    pooled = (stage.groupby(["policy", "condition", "diagnostic_method"], as_index=False)
              .agg(n_fixed_environments=("task", lambda s: stage.loc[s.index, ["task", "split"]].drop_duplicates().shape[0]),
                   n_seed_stage_records=("stage", "size"),
                   **{col: (col, "mean") for col in ["spearman_abs_error_vs_sigma", "mean_sigma",
                      "mean_abs_standardized_residual", "median_abs_standardized_residual",
                      "q90_abs_standardized_residual", "coverage_50", "coverage_80", "coverage_90",
                      "coverage_95", "mace"]}))
    pooled.to_csv(out / "v2_candidate_calibration_equal_weight_summary.csv", index=False)


if __name__ == "__main__":
    main()
