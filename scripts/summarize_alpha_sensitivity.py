from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TAIL_KEYS = {"0p5": "top_0.5pct", "1": "top_1pct", "5": "top_5pct"}
ENVS = (("matbench_expt_gap", "iid_record"),
        ("matbench_mp_gap", "iid_record"),
        ("matbench_mp_gap", "chemical_system_ood"),
        ("matbench_log_kvrh", "chemical_system_ood"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize frozen alpha-sensitivity trajectories and verified V2 RAW baselines.")
    ap.add_argument("--v2-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    source, out = a.v2_root.resolve(), a.out.resolve()
    manifest = pd.read_csv(out / "alpha_sensitivity_run_manifest.csv")
    if len(manifest) != 640 or manifest.status.ne("complete").any() or manifest.job_id.duplicated().any():
        raise ValueError("alpha manifest is not complete and unique")
    protocol = json.loads((out / "ALPHA_SENSITIVITY_PROTOCOL.json").read_text(encoding="utf-8"))
    raw_manifest = pd.read_csv(out / "alpha_raw_baseline_manifest.csv")
    raw_lookup = {}
    for r in raw_manifest.itertuples(index=False):
        f = source / r.result_path
        if sha(f) != r.result_sha256:
            raise ValueError(f"RAW baseline hash mismatch: {r.job_id}")
        raw_lookup[(r.task, r.split, int(r.seed), r.policy)] = json.loads(f.read_text(encoding="utf-8"))
    rows = []
    for r in manifest.itertuples(index=False):
        result_path = out / r.result_path
        if sha(result_path) != r.result_sha256:
            raise ValueError(f"alpha result hash mismatch: {r.job_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        baseline = raw_lookup[(r.task, r.split, int(r.seed), r.policy)]
        rec = {"alpha": float(r.alpha), "task": r.task, "split": r.split,
               "seed": int(r.seed), "policy": r.policy,
               "initial_disagreement": float(result["initial_selection_disagreement_vs_counterfactual"]),
               "mean_diagnostic_mace_raw_on_local_path": float(result["mean_diagnostic_mace_raw"]),
               "mean_diagnostic_mace_local": float(result["mean_diagnostic_mace_local"]),
               "raw_baseline_mace": float(baseline["mean_diagnostic_mace_raw"]),
               "raw_l1": float(baseline["tail_integrated_recall"]["top_1pct"])}
        for tail, key in TAIL_KEYS.items():
            rec[f"local_{tail}"] = float(result["tail_integrated_recall"][key])
            rec[f"raw_{tail}"] = float(baseline["tail_integrated_recall"][key])
            rec[f"difference_{tail}"] = rec[f"local_{tail}"] - rec[f"raw_{tail}"]
        rows.append(rec)
    seed_rows = pd.DataFrame(rows)
    seed_rows.to_csv(out / "alpha_sensitivity_seed_environment.csv", index=False)
    effect_cols = [f"difference_{x}" for x in TAIL_KEYS]
    env_rows = []
    for keys, g in seed_rows.groupby(["alpha", "task", "split", "policy"], sort=True):
        alpha, task, split, policy = keys
        for tail in TAIL_KEYS:
            x = g[f"difference_{tail}"].to_numpy(float)
            env_rows.append({"alpha": alpha, "task": task, "split": split, "policy": policy, "tail": tail,
                             "mean_local_minus_raw": float(x.mean()), "sd_across_20_seeds": float(x.std(ddof=1)),
                             "seed_min": float(x.min()), "seed_max": float(x.max()),
                             "positive_seeds": int((x > 0).sum()), "n_seeds": len(x),
                             "mean_initial_disagreement": float(g.initial_disagreement.mean()),
                             "mean_raw_mace_on_local_path": float(g.mean_diagnostic_mace_raw_on_local_path.mean()),
                             "mean_local_mace": float(g.mean_diagnostic_mace_local.mean()),
                             "mean_raw_baseline_mace": float(g.raw_baseline_mace.mean())})
    environment = pd.DataFrame(env_rows)
    environment.to_csv(out / "alpha_sensitivity_summary.csv", index=False)
    environment.to_csv(out / "supplementary_alpha_table.csv", index=False)
    task_labels = {"matbench_expt_gap": "Expt gap", "matbench_mp_gap": "MP gap",
                   "matbench_log_gvrh": "Log shear (GVRH)", "matbench_log_kvrh": "Log bulk (KVRH)"}
    with (out / "alpha_sensitivity_table.tex").open("w", encoding="utf-8") as f:
        f.write("\\setlength{\\tabcolsep}{3pt}\n\\scriptsize\n")
        f.write("\\begin{longtable}{@{}lllllrrlr@{}}\n")
        f.write("\\caption{Alpha sensitivity across the four prespecified V2 environments.}\\label{tab:alpha_sensitivity}\\\\\n")
        f.write("\\toprule\n$\\alpha$ & Task & Split & Policy & Tail & Mean $\\Delta$ & SD & Seed range & Positive/$n$ \\\\\n\\midrule\n\\endfirsthead\n")
        f.write("\\caption[]{Alpha sensitivity across the four prespecified V2 environments (continued).}\\\\\n")
        f.write("\\toprule\n$\\alpha$ & Task & Split & Policy & Tail & Mean $\\Delta$ & SD & Seed range & Positive/$n$ \\\\\n\\midrule\n\\endhead\n")
        f.write("\\midrule\\multicolumn{9}{r}{Continued on next page}\\\\\n\\endfoot\n\\bottomrule\\endlastfoot\n")
        for r in environment.sort_values(["alpha", "task", "split", "policy", "tail"]).itertuples(index=False):
            task = task_labels[r.task]
            split = "IID" if r.split == "iid_record" else "chem OOD"
            tail = r.tail.replace("p", ".") + r"\%"
            rng = f"[{r.seed_min:+.3f}, {r.seed_max:+.3f}]"
            f.write(f"{r.alpha:.2f} & {task} & {split} & {r.policy.capitalize()} & {tail} & {r.mean_local_minus_raw:+.3f} & {r.sd_across_20_seeds:.3f} & {rng} & {r.positive_seeds}/20 \\\\\n")
        f.write("\\end{longtable}\n")

    pooled_seed = (seed_rows.groupby(["alpha", "policy", "seed"], as_index=False)[effect_cols].mean())
    pooled_seed.to_csv(out / "alpha_sensitivity_equal_weight_seed_means.csv", index=False)
    pooled_rows = []
    for (alpha, policy), g in pooled_seed.groupby(["alpha", "policy"], sort=True):
        for tail in TAIL_KEYS:
            x = g[f"difference_{tail}"].to_numpy(float)
            pooled_rows.append({"alpha": alpha, "policy": policy, "tail": tail,
                                "mean_equal_weight_four_environment_difference": float(x.mean()),
                                "sd_across_20_seed_blocks": float(x.std(ddof=1)),
                                "seed_min": float(x.min()), "seed_max": float(x.max()),
                                "positive_seed_blocks": int((x > 0).sum()), "n_seed_blocks": len(x)})
    pd.DataFrame(pooled_rows).to_csv(out / "alpha_sensitivity_pooled_summary.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5), sharey=True)
    alpha_levels = sorted(seed_rows.alpha.unique())
    env_order = list(ENVS)
    colors = ["#2676A5", "#C05A3D", "#3B8C68", "#805CA5"]
    for ax, policy in zip(axes, ("rank", "magnitude")):
        # `DataFrame.tail` is a method; index the column explicitly.
        sub = environment[(environment.policy == policy) & (environment["tail"] == "1")]
        for (task, split), color in zip(env_order, colors):
            g = sub[(sub.task == task) & (sub.split == split)].sort_values("alpha")
            ax.plot(g.alpha, g.mean_local_minus_raw, marker="o", color=color,
                    label=f"{task_labels[task]}, {'IID' if split == 'iid_record' else 'chem OOD'}")
        ax.axhline(0, color="#555555", linewidth=0.9)
        ax.set_xticks(alpha_levels, [f"{x:.2f}" for x in alpha_levels])
        ax.set_xlabel("Geometric interpolation exponent $\\alpha$")
        ax.set_title(f"{policy.capitalize()} acquisition")
        ax.grid(axis="y", color="#dddddd", linewidth=0.6)
    axes[0].set_ylabel("LOCAL($\\alpha$) $-$ RAW integrated top-1% recall")
    axes[1].legend(frameon=False, fontsize=8, loc="best")
    fig.suptitle("Secondary alpha sensitivity: environment means over 20 paired seeds\nPoints show means; no intervals or hypothesis tests")
    fig.tight_layout()
    fig.savefig(out / "alpha_sensitivity.pdf", bbox_inches="tight")
    plt.close(fig)
    (out / "alpha_sensitivity_summary_metadata.json").write_text(json.dumps({
        "analysis_class": "SECONDARY ALPHA-SENSITIVITY ANALYSIS",
        "protocol_sha256": sha(out / "ALPHA_SENSITIVITY_PROTOCOL.json"),
        "run_manifest_sha256": sha(out / "alpha_sensitivity_run_manifest.csv"),
        "rows": len(manifest), "complete": int(manifest.status.eq("complete").sum()),
        "source_v2_protocol_sha256": protocol["source_v2_protocol_sha256"],
        "positive_seed_count_is_descriptive": True,
        "p_values": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
