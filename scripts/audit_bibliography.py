#!/usr/bin/env python3
"""Check citation-key coverage between the manuscript, SI, BibTeX, and BBL files."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEX_FILES = ("manuscript.tex", "supplementary_information.tex")
BIB_RE = re.compile(r"^@(\w+)\s*[{(]\s*([^,\s]+)\s*,", re.MULTILINE)
CITE_RE = re.compile(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\s*\{([^}]*)\}")
AUX_CITE_RE = re.compile(r"^\\citation\{([^}]*)\}", re.MULTILINE)
BBL_RE = re.compile(r"\\bibitem(?:\[[^]]*\])?\s*\{([^}]*)\}")


def main() -> None:
    bib_text = (ROOT / "bibliography.bib").read_text(encoding="utf-8")
    bib_keys = BIB_RE.findall(bib_text)
    all_keys = [key for _, key in bib_keys]
    cited: set[str] = set()
    aux_cited: set[str] = set()
    aux_keys_by_tex: dict[str, set[str]] = {}
    bbl_keys: dict[str, list[str]] = {}
    for tex in TEX_FILES:
        text = (ROOT / tex).read_text(encoding="utf-8")
        for match in CITE_RE.findall(text):
            cited.update(key.strip() for key in match.split(",") if key.strip())
        aux = ROOT / tex.replace(".tex", ".aux")
        bbl = ROOT / tex.replace(".tex", ".bbl")
        file_aux_keys: set[str] = set()
        if aux.is_file():
            aux_text = aux.read_text(encoding="utf-8", errors="replace")
            for match in AUX_CITE_RE.findall(aux_text):
                file_aux_keys.update(key.strip() for key in match.split(",") if key.strip())
        aux_cited.update(file_aux_keys)
        aux_keys_by_tex[tex] = file_aux_keys
        bbl_keys[tex] = BBL_RE.findall(bbl.read_text(encoding="utf-8", errors="replace")) if bbl.is_file() else []

    key_set = set(all_keys)
    report = {
        "bib_entry_count": len(all_keys),
        "duplicate_bib_keys": sorted(key for key in key_set if all_keys.count(key) > 1),
        "source_citation_keys": sorted(cited),
        "aux_citation_keys": sorted(aux_cited),
        "citation_vs_aux_symmetric_difference": sorted(cited ^ aux_cited),
        "missing_bib_keys": sorted((cited | aux_cited) - key_set),
        "uncited_bib_keys": sorted(key_set - (cited | aux_cited)),
        "bbl_keys": bbl_keys,
        "bbl_vs_aux_symmetric_difference": {
            tex: sorted(set(bbl_keys[tex]) ^ aux_keys_by_tex[tex])
            for tex in TEX_FILES
        },
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if (
        report["duplicate_bib_keys"]
        or report["missing_bib_keys"]
        or report["citation_vs_aux_symmetric_difference"]
        or any(report["bbl_vs_aux_symmetric_difference"].values())
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
