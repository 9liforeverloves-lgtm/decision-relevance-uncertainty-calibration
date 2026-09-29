# Third-party data and redistribution scope

## Dataset identifiers and providers

The analyses use Matbench task identifiers including `matbench_expt_gap`, `matbench_mp_gap`, `matbench_log_gvrh`, and `matbench_log_kvrh`. Obtain source inputs from the [official Matbench documentation](https://docs.materialsproject.org/services/ml-and-ai-applications/matbench) and the original data providers, and follow each provider's current terms.

Human-readable task mapping:

- `matbench_log_gvrh` = log shear modulus (GVRH)
- `matbench_log_kvrh` = log bulk modulus (KVRH)

The Matbench benchmark paper is cited in `manuscript/bibliography.bib`.

## Excluded from this release

This release excludes raw benchmark tables, third-party source datasets, full third-party record-level copies, candidate-state Parquet files, and complete run trajectories. Redistribution rights for these source and derived record-level materials have not been established. No file of those types is included in the staged package. The repository provides aggregate author-generated summaries, protocol/configuration notes, verification records, and retrieval guidance instead.

This scope decision avoids redistributing files whose permissions are unclear; it does not imply that the excluded material is publicly licensed by this project. See `verification/THIRD_PARTY_DATA_AUDIT.md` for the source-by-source audit record.
