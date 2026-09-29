"""Render the six frozen primary contrast rows from archived aggregate CSV data."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


ORDER = (
    ("rank", "RAW"),
    ("rank", "PERMUTED"),
    ("rank", "MATCHED"),
    ("magnitude", "RAW"),
    ("magnitude", "PERMUTED"),
    ("magnitude", "MATCHED"),
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=root / "analysis" / "primary" / "primary_effects.csv")
    parser.add_argument("--output", type=Path, default=root / "tables" / "primary_table1.tex")
    args = parser.parse_args()

    rows: dict[tuple[str, str], dict[str, str]] = {}
    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("metric") != "L4_query" or row.get("left") != "LOCAL":
                continue
            key = (row["rule"].lower(), row["right"].upper())
            if key in rows:
                raise ValueError(f"duplicate frozen primary row: {key}")
            rows[key] = row
    if set(rows) != set(ORDER):
        raise ValueError(f"expected exactly the six frozen LOCAL contrasts; found {sorted(rows)}")

    output = [
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{Prespecified paired-seed contrasts in integrated top-1\% recall over the query budget (\Lfourq).}",
        r"\label{tab:effects}",
        r"\small",
        r"\nesizebox{\linewidth}{!}{%",
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Acquisition & Contrast & Mean difference & 95\% CI & Holm \(p_{\mathrm{adj}}\) & Positive seeds & \(n\)\\",
        r"\midrule",
    ]
    for rule, comparator in ORDER:
        row = rows[(rule, comparator)]
        n = int(row["n_seed"])
        if n != 40:
            raise ValueError(f"frozen primary seed count changed for {(rule, comparator)}: {n}")
        positive = round(float(row["positive_seed_fraction"]) * n)
        acquisition = "Rank" if rule == "rank" else "Magnitude"
        mean = float(row["mean_delta"])
        low = float(row["ci95_low"])
        high = float(row["ci95_high"])
        q_value = float(row["holm_q_two_sided"])
        output.append(
            f"{acquisition} & LOCAL $-$ {comparator} & {mean:.4f} & "
            f"[{low:.4f}, {high:.4f}] & {q_value:.5f} & {positive}/{n} & {n}" + r"\\"
        )
    output.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"}%",
            r"\begin{flushleft}\footnotesize Differences are LOCAL minus comparator. Confidence intervals are percentile-bootstrap intervals over paired seed blocks. Holm-adjusted \(p_{\mathrm{adj}}\) values derive from two-sided sign-flip tests across the six primary contrasts. Positive seeds count seed-level differences greater than zero.\end{flushleft}",
            r"\end{table}",
            "",
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(output), encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
