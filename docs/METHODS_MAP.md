# Methods and artifact map

| Evidence class | Protocol or source | Packaged output | Reproduction boundary |
|---|---|---|---|
| Frozen primary confirmation | `primary_protocol/` and frozen confirmation description in `manuscript/manuscript.tex` | `analysis/primary/primary_effects.csv`, `primary_reproduction_check.csv`, and the manuscript Table 1 | Aggregate effects can be inspected and checked against the manuscript; per-seed records needed to rerun the inferential analysis are not distributed. |
| V2 secondary robustness | `v2_protocol/V2_PROTOCOL.md` and `.json` | `analysis/v2_secondary/` and V2 manuscript/SI figures | Descriptive outputs are included; candidate-state and full run-level inputs are excluded. |
| Alpha sensitivity | `configs/ALPHA_SENSITIVITY_PROTOCOL.json` | `analysis/alpha_sensitivity/` and alpha manuscript/SI figures | The alpha summaries are included; the summarizer requires the per-seed trajectories and RAW baseline records, which are excluded. Alpha=0.5 remains the frozen primary setting. |
| Exploratory diagnostics | Described and labeled in manuscript and SI | Relevant figures and tables in `figures/`, `tables/`, and `manuscript/` | These are descriptive or exploratory outputs, not confirmatory evidence. |

The top-level `SHA256SUMS.txt` verifies the staged file payload. `verification/` contains numerical, bibliography, cross-reference, and third-party data audit records. No new scientific campaign is required or implied by these reproduction instructions.
