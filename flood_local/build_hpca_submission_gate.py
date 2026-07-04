#!/usr/bin/env python3
"""Build HPCA-facing data gates from readiness-labeled workload rows."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


MAIN_ALLOWED = {"B_direct_rtl_clean_workload_row"}
APPENDIX_ALLOWED_PREFIX = "C_projection_"


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def split_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    main: list[dict[str, str]] = []
    appendix: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    for row in rows:
        grade = row.get("readiness_grade", "")
        if grade in MAIN_ALLOWED:
            main.append(row)
        elif grade.startswith(APPENDIX_ALLOWED_PREFIX):
            appendix.append(row)
        else:
            blocked.append(row)
    return main, appendix, blocked


def summarize(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(row.get("readiness_grade", "unknown"), []).append(row)
    out: list[dict[str, Any]] = []
    for grade, items in sorted(groups.items()):
        out.append(
            {
                "readiness_grade": grade,
                "rows": len(items),
                "pytorchsim_cycles": round(sum(float(row.get("pytorchsim_cycles") or 0) for row in items), 4),
                "group16_v7_cycles": round(sum(float(row.get("group16_v7_cycles") or 0) for row in items), 4),
            }
        )
    return out


def write_readme(path: Path, main: list[dict[str, str]], appendix: list[dict[str, str]], blocked: list[dict[str, str]]) -> None:
    main_bad = [row for row in main if row.get("readiness_grade") not in MAIN_ALLOWED]
    appendix_bad = [row for row in appendix if not row.get("readiness_grade", "").startswith(APPENDIX_ALLOWED_PREFIX)]
    status = "PASS" if not main_bad and not appendix_bad else "FAIL"

    with path.open("w", encoding="utf-8") as fh:
        fh.write("# HPCA submission data gate v1\n\n")
        fh.write("## Gate status\n\n")
        fh.write(f"- status: {status}\n")
        fh.write(f"- main table rows: {len(main)}\n")
        fh.write(f"- appendix projection rows: {len(appendix)}\n")
        fh.write(f"- blocked/excluded rows: {len(blocked)}\n\n")
        fh.write("## Main-table rule\n\n")
        fh.write(
            "Only `B_direct_rtl_clean_workload_row` is allowed in the main performance table. "
            "C-level rows may be used only in an explicitly labeled projection/appendix table. "
            "D-level rows are diagnostic evidence and must not be plotted as valid performance data.\n\n"
        )
        fh.write("## Files\n\n")
        fh.write("- `main_table_rows.csv`: direct RTL-clean rows only.\n")
        fh.write("- `appendix_projection_rows.csv`: C-level projection rows only.\n")
        fh.write("- `blocked_or_excluded_rows.csv`: D-level blocked/excluded/boundary rows.\n")
        fh.write("- `gate_summary.csv`: grouped row counts and cycle totals.\n\n")
        fh.write("## Why this matters\n\n")
        fh.write(
            "Several direct RTL attempts matched the predicted cycle count but failed XPROBE output validity. "
            "This gate prevents those rows from entering the HPCA main performance table by accident.\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = read_csv(args.readiness)
    main_rows, appendix_rows, blocked_rows = split_rows(rows)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "main_table_rows.csv", main_rows)
    write_csv(out_dir / "appendix_projection_rows.csv", appendix_rows)
    write_csv(out_dir / "blocked_or_excluded_rows.csv", blocked_rows)
    write_csv(out_dir / "gate_summary.csv", summarize(rows))
    write_readme(out_dir / "README.md", main_rows, appendix_rows, blocked_rows)
    print(f"wrote HPCA submission gate to {out_dir}")


if __name__ == "__main__":
    main()
