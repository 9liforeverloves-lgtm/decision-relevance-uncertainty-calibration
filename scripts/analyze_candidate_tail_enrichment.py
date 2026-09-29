from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TAILS = {"0p5": "top_tail_0p5", "1": "top_tail_1", "5": "top_tail_5"}
COLS = ["task", "split", "seed", "policy", "condition", "stage", "material_id",
        "true_y_retrospective", "selected_flag", "query_order",
        "top_tail_0p5", "top_tail_1", "top_tail_5", "target_labels_used_for_acquisition"]


def summarize_pair(raw: pd.DataFrame, local: pd.DataFrame, context: dict,
                   target_percentile: dict[str, float]) -> tuple[list[dict], list[dict]]:
    if raw.material_id.duplicated().any() or local.material_id.duplicated().any():
        raise ValueError("candidate IDs are not unique within a stored stage")
    if raw.target_labels_used_for_acquisition.astype(bool).any() or local.target_labels_used_for_acquisition.astype(bool).any():
        raise ValueError("target-label noninterference flag is not false")
    if raw.stage.iloc[0] != local.stage.iloc[0]:
        raise ValueError("paired stages do not match")
    stage = int(raw.stage.iloc[0])
    rsel = set(raw.loc[raw.query_order.gt(0), "material_id"].astype(str))
    lsel = set(local.loc[local.query_order.gt(0), "material_id"].astype(str))
    rtruth = raw.set_index(raw.material_id.astype(str))["true_y_retrospective"]
    ltruth = local.set_index(local.material_id.astype(str))["true_y_retrospective"]
    both = len(lsel & rsel)
    lonly, ronly = lsel - rsel, rsel - lsel
    lflags = local.assign(material_id=local.material_id.astype(str)).set_index("material_id")
    rflags = raw.assign(material_id=raw.material_id.astype(str)).set_index("material_id")
    out, details = [], []
    for material_id in sorted(lsel & rsel):
        details.append({**context, "stage": stage, "selection_side": "selected_by_both",
                        "material_id": material_id, "target_percentile": target_percentile[material_id],
                        "true_y_retrospective": float(ltruth.loc[material_id]),
                        **{tail: bool(lflags.at[material_id, flag]) for tail, flag in TAILS.items()}})
    for side, chosen, frame, truth in (("local_only", lonly, lflags, ltruth), ("raw_only", ronly, rflags, rtruth)):
        for material_id in sorted(chosen):
            details.append({**context, "stage": stage, "selection_side": side,
                            "material_id": material_id, "target_percentile": target_percentile[material_id],
                            "true_y_retrospective": float(truth.loc[material_id]),
                            **{tail: bool(frame.at[material_id, flag]) for tail, flag in TAILS.items()}})
    for tail, flag in TAILS.items():
        ld = [x for x in details if x["selection_side"] == "local_only"]
        rd = [x for x in details if x["selection_side"] == "raw_only"]
        lc = np.array([x[tail] for x in ld], dtype=bool)
        rc = np.array([x[tail] for x in rd], dtype=bool)
        lrate = float(lc.mean()) if len(lc) else np.nan
        rrate = float(rc.mean()) if len(rc) else np.nan
        lpct = np.asarray([x["target_percentile"] for x in ld], dtype=float)
        rpct = np.asarray([x["target_percentile"] for x in rd], dtype=float)
        lvalues = np.asarray([x["true_y_retrospective"] for x in ld], dtype=float)
        rvalues = np.asarray([x["true_y_retrospective"] for x in rd], dtype=float)
        out.append({**context, "stage": stage, "tail": tail, "selected_by_both_count": both,
                    "local_only_count": len(lonly), "raw_only_count": len(ronly),
                    "local_only_tail_count": int(lc.sum()), "raw_only_tail_count": int(rc.sum()),
                    "local_only_tail_fraction": lrate, "raw_only_tail_fraction": rrate,
                    "tail_fraction_difference": lrate - rrate if np.isfinite(lrate) and np.isfinite(rrate) else np.nan,
                    "enrichment_ratio": lrate / rrate if np.isfinite(lrate) and np.isfinite(rrate) and rrate > 0 else np.nan,
                    "local_only_target_percentile_mean": float(lpct.mean()) if len(lpct) else np.nan,
                    "raw_only_target_percentile_mean": float(rpct.mean()) if len(rpct) else np.nan,
                    "local_only_target_percentile_median": float(np.median(lpct)) if len(lpct) else np.nan,
                    "raw_only_target_percentile_median": float(np.median(rpct)) if len(rpct) else np.nan,
                    "local_only_target_mean": float(lvalues.mean()) if len(lvalues) else np.nan,
                    "raw_only_target_mean": float(rvalues.mean()) if len(rvalues) else np.nan,
                    "local_only_target_median": float(np.median(lvalues)) if len(lvalues) else np.nan,
                    "raw_only_target_median": float(np.median(rvalues)) if len(rvalues) else np.nan})
    return out, details


def aggregate(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    records = []
    for vals, g in df.groupby(keys, dropna=False, sort=True):
        vals = vals if isinstance(vals, tuple) else (vals,)
        row = dict(zip(keys, vals))
        for side in ("local_only", "raw_only"):
            n = int(g[f"{side}_count"].sum())
            tails = int(g[f"{side}_tail_count"].sum())
            row[f"{side}_count"] = n
            row[f"{side}_tail_count"] = tails
            row[f"{side}_tail_fraction"] = tails / n if n else np.nan
        row["selected_by_both_count"] = int(g.selected_by_both_count.sum())
        lf, rf = row["local_only_tail_fraction"], row["raw_only_tail_fraction"]
        row["tail_fraction_difference"] = lf - rf if np.isfinite(lf) and np.isfinite(rf) else np.nan
        row["enrichment_ratio"] = lf / rf if np.isfinite(lf) and np.isfinite(rf) and rf > 0 else np.nan
        records.append(row)
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrospective V2 entrant-tail enrichment; descriptive only.")
    parser.add_argument("--v2-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.v2_root.resolve(), args.out.resolve()
    manifest = pd.read_csv(root / "V2_RUN_MANIFEST.csv")
    if len(manifest) != 640 or manifest.status.ne("complete").any() or manifest.job_id.duplicated().any():
        raise ValueError("V2 manifest is not the verified 640-job complete manifest")
    out.mkdir(parents=True, exist_ok=True)
    contexts = manifest[["task", "split", "seed", "policy", "condition", "candidate_state_path"]]
    lookup = {(r.task, r.split, int(r.seed), r.policy, r.condition): root / r.candidate_state_path
              for r in contexts.itertuples(index=False)}
    rows, candidate_details = [], []
    for task in sorted(manifest.task.unique()):
        for split in sorted(manifest.split.unique()):
            for seed in sorted(manifest.seed.unique()):
                for policy in ("rank", "magnitude"):
                    for stage in range(4):
                        rp = lookup[(task, split, int(seed), policy, "RAW")] / f"stage_{stage}.parquet"
                        lp = lookup[(task, split, int(seed), policy, "LOCAL")] / f"stage_{stage}.parquet"
                        if not rp.is_file() or not lp.is_file():
                            raise FileNotFoundError(f"missing verified candidate stage: {rp} or {lp}")
                        raw, local = pd.read_parquet(rp, columns=COLS), pd.read_parquet(lp, columns=COLS)
                        if int(raw.seed.iloc[0]) != int(seed) or int(local.seed.iloc[0]) != int(seed):
                            raise ValueError("candidate seed does not match manifest")
                        if raw.stage.nunique() != 1 or local.stage.nunique() != 1:
                            raise ValueError("mixed campaign stages in Parquet")
                        if stage == 0:
                            if set(raw.material_id.astype(str)) != set(local.material_id.astype(str)):
                                raise ValueError("paired stage-0 candidate pools differ")
                            if not np.array_equal(raw.true_y_retrospective.to_numpy(float), local.true_y_retrospective.to_numpy(float)):
                                raise ValueError("paired stage-0 labels differ in stored row order")
                            ordered = raw.assign(material_id=raw.material_id.astype(str)).sort_values(
                                ["true_y_retrospective", "material_id"], ascending=[False, True], kind="mergesort")
                            n_target = len(ordered)
                            pct = np.ones(n_target, dtype=float) if n_target == 1 else 1.0 - np.arange(n_target) / (n_target - 1)
                            target_percentile = dict(zip(ordered.material_id.astype(str), pct))
                        ctx = {"task": task, "split": split, "seed": int(seed), "policy": policy}
                        summaries, detail = summarize_pair(raw, local, ctx, target_percentile)
                        rows.extend(summaries)
                        candidate_details.extend(detail)
    seed_stage = pd.DataFrame(rows)
    seed_stage.to_csv(out / "candidate_enrichment_seed_stage.csv", index=False)
    details = pd.DataFrame(candidate_details)
    details.to_parquet(out / "candidate_enrichment_selection_membership.parquet", index=False, compression="zstd")

    def attach_candidate_stats(summary: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
        stat_keys = [k for k in keys if k != "tail"]
        stats = []
        for vals, g in details.groupby(stat_keys + ["selection_side"], dropna=False, sort=True):
            vals = vals if isinstance(vals, tuple) else (vals,)
            row = dict(zip(stat_keys + ["selection_side"], vals))
            row["target_percentile_mean"] = float(g.target_percentile.mean())
            row["target_percentile_median"] = float(g.target_percentile.median())
            row["target_value_mean"] = float(g.true_y_retrospective.mean())
            row["target_value_median"] = float(g.true_y_retrospective.median())
            stats.append(row)
        stat = pd.DataFrame(stats)
        for side in ("local_only", "raw_only"):
            ss = stat[stat.selection_side.eq(side)].drop(columns="selection_side").rename(columns={
                "target_percentile_mean": f"{side}_target_percentile_mean",
                "target_percentile_median": f"{side}_target_percentile_median",
                "target_value_mean": f"{side}_target_mean",
                "target_value_median": f"{side}_target_median"})
            summary = summary.merge(ss, on=stat_keys, how="left", validate="many_to_one")
        return summary

    stage_table = aggregate(seed_stage, ["task", "split", "policy", "stage", "tail"])
    stage_table = attach_candidate_stats(stage_table, ["task", "split", "policy", "stage", "tail"])
    stage_table.to_csv(out / "candidate_enrichment_environment_stage.csv", index=False)
    environment = aggregate(seed_stage, ["task", "split", "policy", "tail"])
    environment = attach_candidate_stats(environment, ["task", "split", "policy", "tail"])
    environment.to_csv(out / "S_new_candidate_enrichment.csv", index=False)

    pooled_rows = []
    for (policy, tail), g in environment.groupby(["policy", "tail"], sort=True):
        for metric in ("local_only_tail_fraction", "raw_only_tail_fraction", "tail_fraction_difference", "enrichment_ratio"):
            x = g[metric].dropna().to_numpy(float)
            pooled_rows.append({"policy": policy, "tail": tail, "metric": metric,
                                "equal_weight_environment_mean": float(x.mean()) if len(x) else np.nan,
                                "environment_sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
                                "environment_min": float(x.min()) if len(x) else np.nan,
                                "environment_max": float(x.max()) if len(x) else np.nan,
                                "n_fixed_environments": len(x)})
    pd.DataFrame(pooled_rows).to_csv(out / "candidate_enrichment_equal_weight_summary.csv", index=False)

    short_task = {"matbench_expt_gap": "Expt", "matbench_mp_gap": "MP",
                  "matbench_log_gvrh": "GVRH", "matbench_log_kvrh": "KVRH"}
    full_task = {"matbench_expt_gap": "Expt gap", "matbench_mp_gap": "MP gap",
                 "matbench_log_gvrh": "Log shear (GVRH)", "matbench_log_kvrh": "Log bulk (KVRH)"}
    labels = [f"{short_task[r.task]}\n{'IID' if r.split == 'iid_record' else 'chem OOD'}"
              for r in environment.drop_duplicates(["task", "split"]).itertuples()]
    env_order = environment[["task", "split"]].drop_duplicates().sort_values(["task", "split"])
    xloc = np.arange(len(env_order))
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharey=True)
    colors = {"0p5": "#2676A5", "1": "#C05A3D", "5": "#3B8C68"}
    markers = {"0p5": "o", "1": "s", "5": "^"}
    for ax, policy in zip(axes, ("rank", "magnitude")):
        sub = environment[environment.policy.eq(policy)]
        for tail in TAILS:
            t = sub[sub["tail"].eq(tail)].sort_values(["task", "split"])
            ax.plot(xloc, t.tail_fraction_difference, marker=markers[tail], linestyle="none",
                    color=colors[tail], label=f"Top {tail.replace('p','.') }%", markersize=6)
        ax.axhline(0, color="#555555", linewidth=0.9)
        ax.set_xticks(xloc, labels, rotation=0, ha="center")
        ax.tick_params(axis="x", labelsize=8)
        ax.set_title(f"{policy.capitalize()} acquisition")
        ax.set_ylabel("LOCAL-only minus RAW-only tail fraction")
        ax.grid(axis="y", color="#dddddd", linewidth=0.6)
    axes[1].set_ylabel("")
    axes[0].legend(frameon=False, title="Target-pool tail")
    fig.suptitle("Retrospective tail enrichment of exchanged candidates\nV2 secondary diagnostic; environment summaries pool 20 seeds × 4 stages")
    fig.text(0.5, 0.012, "GVRH = log shear modulus; KVRH = log bulk modulus", ha="center", fontsize=8, color="#52606D")
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    fig.savefig(out / "candidate_tail_enrichment.pdf", bbox_inches="tight")
    plt.close(fig)

    # LaTeX-ready SI rows, one row per fixed task--split--policy and tail.
    table = environment.sort_values(["policy", "task", "split", "tail"])
    with (out / "S_new_candidate_enrichment.tex").open("w", encoding="utf-8") as f:
        f.write("\\begin{tabular}{llllrrrrrrr}\n\\toprule\n")
        f.write("Task & Split & Policy & Tail & LOCAL-only $n$ & RAW-only $n$ & Both $n$ & LOCAL tail & RAW tail & $\\Delta$ & Ratio \\\\\n\\midrule\n")
        for r in table.itertuples(index=False):
            task = full_task[r.task]
            split = "IID" if r.split == "iid_record" else "chemical OOD"
            pol = r.policy.capitalize()
            f.write(f"{task} & {split} & {pol} & {r.tail.replace('p','.') }\\% & {r.local_only_count} & {r.raw_only_count} & {r.selected_by_both_count} & {r.local_only_tail_fraction:.3f} & {r.raw_only_tail_fraction:.3f} & {r.tail_fraction_difference:+.3f} & {r.enrichment_ratio:.2f} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")


if __name__ == "__main__":
    main()
