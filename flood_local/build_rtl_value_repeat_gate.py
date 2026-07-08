#!/usr/bin/env python3
"""Gate server RTL repeatability value checks conservatively."""

from __future__ import annotations

import argparse
import csv
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


def as_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "0") or 0))
    except ValueError:
        return 0


def build_gate(prepare_summary_csv: Path, value_summary_csv: Path, out_dir: Path) -> None:
    prepare = read_rows(prepare_summary_csv)
    values = read_rows(value_summary_csv)
    prepare_row = prepare[0] if prepare else {}
    gate_rows: list[dict[str, str]] = []
    for row in values:
        passed = row.get("value_check_status") == "pass" and as_int(row, "compared_values") > 0
        gate_rows.append(
            {
                "workload_id": row.get("workload_id", ""),
                "value_check_status": row.get("value_check_status", ""),
                "compared_values": row.get("compared_values", "0"),
                "num_mismatches": row.get("num_mismatches", ""),
                "repeat_value_policy": "repeatability_pass" if passed else "repeatability_fail",
                "ready_for_direct_paper_data": "no",
                "paper_data_blocker": "golden_is_prior_rtl_repeat_not_independent_software_reference",
            }
        )

    passed_cases = sum(1 for row in gate_rows if row["repeat_value_policy"] == "repeatability_pass")
    total_compared = sum(as_int(row, "compared_values") for row in values)
    status = "pass" if prepare_row.get("prepare_status") == "pass" and values and passed_cases == len(values) else "missing_or_failed"
    summary = [
        {
            "repeat_value_gate_status": status,
            "prepared_cases": prepare_row.get("ready_cases", "0"),
            "checked_cases": str(len(values)),
            "passed_cases": str(passed_cases),
            "total_compared_values": str(total_compared),
            "direct_paper_ready_cases": "0",
            "paper_data_policy": "repeatability_only_not_independent_golden",
            "main_blocker": "independent software golden reference still required for paper value correctness",
        }
    ]

    write_csv(out_dir / "rtl_value_repeat_gate.csv", gate_rows)
    write_csv(out_dir / "rtl_value_repeat_gate_summary.csv", summary)
    readme = """# RTL Value Repeat Gate

This gate wraps server RTL repeat value checks. A passing row means two separate
RTL executions produced identical numeric outputs for the same tile case.

This is useful repeatability evidence, but it is not an independent software
golden reference. Therefore `direct_paper_ready_cases` remains zero.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prepare-summary",
        default="results/flood_cycle_sim_v1/rtl_value_repeat_prepare/value_repeat_prepare_summary.csv",
    )
    parser.add_argument(
        "--value-summary",
        default="results/flood_cycle_sim_v1/rtl_value_repeat_check/merged_value_check_summary.csv",
    )
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/rtl_value_repeat_gate")
    args = parser.parse_args()
    build_gate(Path(args.prepare_summary), Path(args.value_summary), Path(args.out_dir))


if __name__ == "__main__":
    main()
