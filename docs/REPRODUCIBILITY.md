# Reproducibility

This release candidate supports integrity checks, inspection of archived aggregate outputs, and rebuilding the manuscript and SI from their included sources and assets. It does not contain complete run-level records or all campaign inputs; it therefore does not support an exact end-to-end rerun of every analysis.

## Lightweight reproduction

Run from the repository root.

### Integrity check

```powershell
python scripts/generate_sha256_manifest.py
python scripts/verify_sha256.py SHA256SUMS.txt
```

### Rebuild the manuscript and SI PDFs

Requires XeLaTeX and BibTeX. Each command is run from the repository root:

```powershell
xelatex manuscript/manuscript.tex
bibtex manuscript
xelatex manuscript/manuscript.tex
xelatex manuscript/manuscript.tex
Copy-Item manuscript.pdf manuscript/manuscript.pdf -Force

xelatex manuscript/supplementary_information.tex
bibtex supplementary_information
xelatex manuscript/supplementary_information.tex
xelatex manuscript/supplementary_information.tex
Copy-Item supplementary_information.pdf manuscript/supplementary_information.pdf -Force
```

The source uses the included figures, tables, and bibliography. This rebuilds the documents from packaged source and assets; it does not regenerate the figures from run-level observations.

### Inspect archived primary values

`analysis/primary/primary_effects.csv` and `analysis/primary/primary_reproduction_check.csv` contain the archived six confirmatory contrasts and the frozen-authority comparison. Regenerate the manuscript's six-row Table 1 directly from the frozen aggregate CSV:

```powershell
python scripts/regenerate_primary_table.py
```

The manuscript reports the LOCAL−RAW top-1% effects as rank +0.0190 (95% CI [0.0122, 0.0259]) and magnitude +0.0144 (95% CI [0.0083, 0.0206]). This command formats archived estimates; it does not rerun the seed-level bootstrap or other statistical tests. The run-level observations needed for those operations are not distributed.

The manuscript PDFs include the primary figures, supplementary figures, and tables as compiled publication outputs. Recompiling the TeX sources incorporates all packaged figures and tables. Plot-generation scripts that require raw candidate records cannot regenerate those visualizations from the included aggregate summaries alone.

## Analysis classes and available outputs

1. **Frozen primary confirmation:** six prespecified contrasts, the primary endpoint, and the 40-seed confirmation remain unchanged. Aggregate outputs are in `analysis/primary/`.
2. **V2 secondary robustness:** descriptive summaries are in `analysis/v2_secondary/`. Scripts that rebuild them require candidate-level V2 inputs not included here.
3. **Alpha sensitivity:** the frozen primary calibration setting remains alpha=0.5; the sensitivity summaries are in `analysis/alpha_sensitivity/`. The summarizer also requires the 640 per-seed result files and RAW baseline records, which are not included.
4. **Exploratory diagnostics:** figures and the supported aggregate outputs are included where identified in the manuscript and SI. These are not confirmatory evidence.

The commands for `scripts/analyze_v2_candidate_calibration.py`, `scripts/analyze_candidate_tail_enrichment.py`, and `scripts/summarize_alpha_sensitivity.py` require external run-level inputs and are not executable with this sanitized package alone. No experimental or campaign job should be launched to validate this documentation.

## Full campaign rerun

A full rerun requires provider benchmark data, split membership, campaign configuration, candidate-state records, and per-seed results. Full run-level records and candidate-state Parquet files are not distributed because redistribution rights have not been established. Obtain source datasets from their original providers, confirm applicable terms, and use only authorized inputs. This repository does not claim exact full-campaign reproducibility or provide runtime estimates.
