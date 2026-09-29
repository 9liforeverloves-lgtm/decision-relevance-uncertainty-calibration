# V2 protocol: second-surrogate and tail robustness

**Status: V2.1 operational amendment frozen before the full campaign.** The scientific design was frozen on 2026-09-26. After the dry-run repeat canary, V2.1 corrected only `state_fingerprint` serialization: Python object-array memory bytes produced run-specific hashes despite identical candidate states. The amendment serializes IDs as UTF-8 and numeric arrays as little-endian float64. It does not change datasets, features, splits, seeds, model, calibration, acquisition, metrics, or analysis. The V2.0 dry-run artifacts remain preserved under `audit/v2_0_dry_run_20260927/`. This independent secondary analysis does not alter or replicate the frozen V5 confirmation.

## Design and data

- Tasks: `matbench_expt_gap`, `matbench_mp_gap`, `matbench_log_gvrh`, `matbench_log_kvrh`.
- Splits: deterministic IID-record and whole-chemical-system OOD; source/diagnostic/target fractions 0.20/0.20/0.60 with minimum partition sizes 30/20/50, respectively.
- Seeds: the 20 fixed integers 2026092600–2026092619 for every task and split. These form a V2-only namespace.
- Dataset identity: the four hashes in `DATA_MANIFEST.md`; these are the archived D-drive CSVs, not a claim of V5 snapshot identity.
- Expected main jobs: 4 tasks × 2 splits × 20 seeds × 2 acquisition policies × 2 conditions = 640 RF trajectories. The two-seed MP-gap/IID dry-run and its repeatability canary are separate from the main result namespace.

## Surrogate, uncertainty, and calibration

The second surrogate is `RandomForestRegressor` with 80 bootstrap trees, minimum leaf size 2, all features available at each split, one worker, and deterministic stage/seed-derived random states. Broad capacity settings match the surviving primary plan; no settings are selected using V2 LOCAL–RAW outcomes. Raw predictive mean is the ensemble mean and raw uncertainty is the population standard deviation (`ddof=0`) of tree predictions. Training-row OOB mean, standard deviation, and counts are computed only from trees whose bootstrap samples excluded that row.

LOCAL uses the archived calibration definition: fit an ExtraTrees regressor (64 trees, minimum leaf size 5) to log absolute OOB residual ratios from currently queried source/target labels; five deterministic ID-hash folds provide an out-of-fold median normalization multiplier; clip candidate local scales to [0.25, 4]; and geometrically interpolate global and local scale with the fixed exponent alpha=0.5. RAW uses unscaled ensemble uncertainty. The calibration fit never receives target-pool labels.

## Acquisition and campaign schedule

- Rank: percentile rank of predicted mean plus percentile rank of uncertainty; stable material-ID tie-breaking.
- Magnitude: predicted mean plus uncertainty; stable material-ID tie-breaking.
- Initial labels: a seeded sample from the source partition, count `max(30, round(0.01 * task_rows))`, capped by source size.
- Four sequential query batches; the total query budget is `max(1, round(0.20 * target_rows))` and is divided as evenly as possible across four updates.
- Each RAW and LOCAL path starts from identical source labels for the same task/split/seed. At each stage the model and calibration are fitted only from labels revealed by that path.

## Outputs, tails, and analyses

The sole V2 campaign endpoint is the trapezoidal integrated recall over query order, evaluated at target-pool top 0.5%, 1%, and 5%. Top-tail membership uses stable material-ID tie-breaking and is computed retrospectively. The 1% value is retained for comparability; it does not replace the frozen primary endpoint. All three thresholds are calculated from the same stored trajectories, with no threshold-specific refits.

Each candidate-state record stores task/split/seed/stage, candidate ID, retrospective true target, predicted mean, raw uncertainty, calibration multiplier, local scale, corrected uncertainty, value/uncertainty ranks, RAW and LOCAL scores/ranks/selections/query order for both policies, top-tail membership, and a state fingerprint. Target labels are attached only after predictions, acquisition ranks, and selected batches have been finalized. The code path and leakage assertions are described in `code/run_v2_campaign.py` and `DRY_RUN_REPORT.md`.

Reports are descriptive paired-seed distributions: means, medians, standard deviations, ranges, and positive-seed fractions. No V2 p-values or inferential claims are planned. Candidate-level uncertainty/error alignment, tail-specific uncertainty and scale, same-state entrants versus displaced candidates, top-tail displacement, and acquisition-rank changes are exploratory V2 diagnostics, with no chemical mechanism claim.

## Freeze and exclusions

No beta or alpha grid is planned. Failed runs are logged and may be retried only with the identical protocol/configuration and seed; no missing run is silently dropped. The split memberships are already frozen in `manifests/v2_split_membership.parquet`. The two-seed dry-run must pass determinism, query count, stable IDs, no leakage, uncertainty/scale validity, output completeness, and a repeated-run hash comparison before the full run. The 20-seed main count remains fixed after the pre-outcome compute/storage gate; no reduction is planned. V2.1 is the version used for the main campaign. The frozen JSON protocol SHA-256 is `16850cceb69b6eac30e5b7ca164793ad296f8684b84b97f9345d68cb42c2b5ab`.
