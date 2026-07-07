#!/usr/bin/env python3
"""Export only final-gate-approved rows for main paper figures."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["status"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_package(final_gate: Path, out_dir: Path) -> None:
    rows = read_rows(final_gate)
    approved = [row for row in rows if row.get("final_paper_data_policy") == "ready_for_main_figure"]
    rejected = [row for row in rows if row.get("final_paper_data_policy") != "ready_for_main_figure"]
    write_csv(out_dir / "main_figure_rows.csv", approved)
    write_csv(out_dir / "rejected_rows.csv", rejected)
    summary = [
        {
            "source_final_gate": str(final_gate),
            "source_final_gate_sha256": sha256_file(final_gate),
            "total_rows": str(len(rows)),
            "exported_main_figure_rows": str(len(approved)),
            "rejected_rows": str(len(rejected)),
            "export_policy": "Only rows with final_paper_data_policy=ready_for_main_figure are exported.",
        }
    ]
    write_csv(out_dir / "export_summary.csv", summary)
    text = f"""# FLOOD Main Figure Export Package

Source final gate: `{final_gate}`

This directory is intentionally strict. `main_figure_rows.csv` contains only
rows whose final gate policy is `ready_for_main_figure`.

Generated files:

- `main_figure_rows.csv`: rows allowed for main paper figures.
- `rejected_rows.csv`: rows blocked by the final gate.
- `export_summary.csv`: source hash and row counts.
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-gate", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    export_package(Path(args.final_gate), Path(args.out_dir))


if __name__ == "__main__":
    main()
