from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


ALPHAS = (0.25, 0.50, 0.75, 1.00)
ENVIRONMENTS = (("matbench_expt_gap", "iid_record"),
                ("matbench_mp_gap", "iid_record"),
                ("matbench_mp_gap", "chemical_system_ood"),
                ("matbench_log_kvrh", "chemical_system_ood"))
POLICIES = ("rank", "magnitude")
SEEDS = tuple(range(2026092600, 2026092620))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="Run independent sequential LOCAL trajectories for the prespecified V2 alpha sensitivity.")
    ap.add_argument("--v2-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--max-jobs", type=int, default=0)
    args = ap.parse_args()
    source = args.v2_root.resolve()
    out = args.out.resolve()
    manifest_path = args.manifest.resolve()
    if not source.is_dir() or not manifest_path.is_relative_to(out):
        raise ValueError("invalid input/output roots")
    out.mkdir(parents=True, exist_ok=True)
    runner_path = source / "code" / "run_v2_campaign.py"
    spec = importlib.util.spec_from_file_location("v2_runner_reference", runner_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not import frozen V2 runner at {runner_path}")
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    original_root = runner.ROOT
    original_load_task = runner.load_task
    original_membership = runner.get_split_membership
    original_state_rows = runner.candidate_state_rows

    def source_loader(task: str):
        runner.ROOT = source
        try:
            return original_load_task(task)
        finally:
            runner.ROOT = out

    def source_membership(task: str, split: str, seed: int, ids: np.ndarray):
        runner.ROOT = source
        try:
            return original_membership(task, split, seed, ids)
        finally:
            runner.ROOT = out

    def alpha_state_rows(**kwargs):
        state = original_state_rows(**kwargs)
        col = f"corrected_sigma_alpha_{str(runner.ALPHA).replace('.', 'p')}"
        state = state.rename(columns={"corrected_sigma_alpha_0p5": col})
        return state

    runner.ROOT = out
    runner.load_task = source_loader
    runner.get_split_membership = source_membership
    runner.candidate_state_rows = alpha_state_rows

    protocol_path = out / "ALPHA_SENSITIVITY_PROTOCOL.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_hash = sha256_file(protocol_path)
    manifest = pd.read_csv(manifest_path, dtype={"status": "string", "result_sha256": "string", "error": "string"})
    pending = manifest.index[manifest.status.eq("planned")].tolist()
    if args.max_jobs:
        pending = pending[:args.max_jobs]
    cache: dict = {}
    for index in pending:
        row = manifest.loc[index]
        start = time.perf_counter()
        try:
            runner.ALPHA = float(row.alpha)
            result = runner.run_one(row, cache)
            result["alpha"] = float(row.alpha)
            result["analysis_class"] = "SECONDARY ALPHA-SENSITIVITY ANALYSIS"
            result["source_v2_protocol_sha256"] = protocol["source_v2_protocol_sha256"]
            result["alpha_protocol_sha256"] = protocol_hash
            result["runtime_seconds"] = time.perf_counter() - start
            result_path = out / str(row.result_path)
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            manifest.loc[index, "status"] = "complete"
            manifest.loc[index, "runtime_seconds"] = result["runtime_seconds"]
            manifest.loc[index, "result_sha256"] = sha256_file(result_path)
            manifest.loc[index, "error"] = ""
            print(json.dumps({"status": "complete", "job_id": row.job_id,
                              "alpha": float(row.alpha), "seconds": round(result["runtime_seconds"], 2),
                              "L1": result["tail_integrated_recall"]["top_1pct"]}, ensure_ascii=False), flush=True)
        except Exception as error:
            manifest.loc[index, "status"] = "failed"
            manifest.loc[index, "error"] = f"{type(error).__name__}: {error}"
            print(json.dumps({"status": "failed", "job_id": row.job_id,
                              "error": manifest.loc[index, "error"]}, ensure_ascii=False), flush=True)
        manifest.to_csv(manifest_path, index=False)
    manifest.to_csv(manifest_path, index=False)
    runner.ROOT = original_root


if __name__ == "__main__":
    main()
