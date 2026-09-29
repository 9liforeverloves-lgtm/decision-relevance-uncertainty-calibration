# Decision Relevance of Uncertainty Calibration in Active-Learning Materials Screening

## Overview

This repository supports a manuscript prepared for submission to *Machine Learning: Science and Technology*. It asks when uncertainty calibration changes candidate selection in a way that improves a task-specific discovery objective. Calibration quality, uncertainty-error ranking, candidate perturbation, and downstream discovery utility are distinct quantities; improvement in one does not guarantee improvement in the next.

Public repository: https://github.com/9liforeverloves-lgtm/decision-relevance-uncertainty-calibration. This repository accompanies a manuscript prepared for submission; it has not been submitted, accepted, or published.

## Main findings

- The frozen pooled primary LOCAL−RAW effects are positive: rank +0.0190 (95% CI [0.0122, 0.0259]) and magnitude +0.0144 (95% CI [0.0083, 0.0206]).
- Both `matbench_mp_gap` splits show negative task-level effects in the frozen primary confirmation.
- V2 descriptive analyses show dependence on acquisition policy and target-tail definition.
- Alpha sensitivity shows that intervention strength affects the direction and size of downstream utility.

These results do not support a universal claim that LOCAL is superior.

## Repository structure

- `manuscript/`: manuscript and SI source, PDFs, bibliography, and figure assets.
- `analysis/`: frozen-primary aggregates and separate V2 and alpha-sensitivity summaries.
- `scripts/`: selected analysis and verification scripts.
- `configs/`: alpha-sensitivity protocol.
- `figures/`, `tables/`: publication figures and supplementary tables.
- `MANIFEST.md`, `manifests/`, `SHA256SUMS.txt`: inclusion/exclusion scope and integrity records.
- `primary_protocol/`, `v2_protocol/`, `verification/`: protocol notes and audits.
- `docs/`: reproduction, data, code, third-party data, methods, and optional Zenodo guidance.

## Reproducibility

See [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md). It distinguishes the frozen primary confirmation, V2 secondary robustness analysis, alpha sensitivity, and exploratory diagnostics. Included aggregate outputs support inspection and integrity checks; this repository does not contain the complete run-level records required to regenerate every analysis from candidate records.

## Data

Raw third-party Matbench tables and candidate-state files are not redistributed. See [docs/DATA_AVAILABILITY.md](docs/DATA_AVAILABILITY.md) for provider retrieval guidance and the permitted scope.

Task labels: `matbench_log_gvrh` means log shear modulus (GVRH); `matbench_log_kvrh` means log bulk modulus (KVRH). The other named tasks include `matbench_expt_gap` and `matbench_mp_gap`.

## Environment

The packaged Python environment is recorded in `requirements.txt` and `ENVIRONMENT.md`. It lists Python 3.12.14 and exact package pins. Manuscript regeneration additionally requires XeLaTeX and BibTeX. The original full-campaign environment and complete lockfiles are not included.

## Citation

See [CITATION.cff](CITATION.cff). No repository DOI is assigned.

## License

The MIT License applies only to original source code in this repository. Third-party packages retain their own licenses; Matbench and other source data are not relicensed here. Manuscript and publication copyright are governed separately by the journal and publication license. See [LICENSE_NOTES.md](LICENSE_NOTES.md).

## Manuscript status

This repository accompanies a manuscript prepared for submission to *Machine Learning: Science and Technology*. It has not been submitted through ScholarOne, accepted, or published.
