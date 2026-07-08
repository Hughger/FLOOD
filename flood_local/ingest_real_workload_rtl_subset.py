#!/usr/bin/env python3
"""Ingest real-workload-derived RTL subset runs into conservative gates."""

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


def classify(row: dict[str, str]) -> str:
    rc = as_int(row, "rc")
    run_count = as_int(row, "run_count")
    x_count = as_int(row, "x_count")
    timeout = (row.get("timeout", "") or "").strip().lower()
    if x_count > 0 or rc not in {0, 124}:
        return "rtl_x_or_error"
    if rc == 0 and run_count > 0 and timeout == "no":
        return "rtl_complete_clean"
    if timeout == "yes" and run_count > 0:
        return "rtl_partial_progress_clean"
    if timeout == "yes" and run_count == 0:
        return "rtl_timeout_no_output"
    return "rtl_x_or_error"


def ingest_subset(input_csv: Path, out_dir: Path) -> None:
    rows = read_rows(input_csv)
    gated: list[dict[str, str]] = []
    for row in rows:
        status = classify(row)
        run_count = as_int(row, "run_count")
        x_count = as_int(row, "x_count")
        ready_for_calibration = status in {"rtl_complete_clean", "rtl_partial_progress_clean"}
        gated.append(
            {
                **row,
                "rtl_subset_status": status,
                "ready_for_calibration": "yes" if ready_for_calibration else "no",
                "ready_for_direct_paper_data": "no",
                "paper_data_blocker": "bounded_mac_wrapper_subset_not_full_chip_value_timing",
                "evidence_scope": "real_workload_derived_mac_wrapper_rtl_subset",
                "quality_note": (
                    "clean_complete_or_partial_cycle_markers"
                    if ready_for_calibration and x_count == 0 and run_count > 0
                    else "no_clean_cycle_marker_output"
                ),
            }
        )

    counts = {
        "rtl_complete_clean": 0,
        "rtl_partial_progress_clean": 0,
        "rtl_timeout_no_output": 0,
        "rtl_x_or_error": 0,
    }
    datasets: set[str] = set()
    real_workload_cases = 0
    for row in gated:
        counts[row["rtl_subset_status"]] = counts.get(row["rtl_subset_status"], 0) + 1
        dataset = row.get("dataset", "")
        if dataset:
            datasets.add(dataset)
        if dataset == "workload_v1":
            real_workload_cases += 1

    calibration_ready = counts["rtl_complete_clean"] + counts["rtl_partial_progress_clean"]
    summary = [
        {
            "ingest_status": "pass" if rows else "missing_input",
            "total_cases": str(len(rows)),
            "datasets": ";".join(sorted(datasets)),
            "real_workload_cases": str(real_workload_cases),
            "complete_clean_cases": str(counts["rtl_complete_clean"]),
            "partial_progress_clean_cases": str(counts["rtl_partial_progress_clean"]),
            "timeout_no_output_cases": str(counts["rtl_timeout_no_output"]),
            "x_or_error_cases": str(counts["rtl_x_or_error"]),
            "calibration_ready_cases": str(calibration_ready),
            "direct_paper_ready_cases": "0",
            "paper_data_policy": "calibration_only_not_direct_paper_data",
            "main_blocker": "not full-chip/full-layer RTL timing and no golden value comparison",
        }
    ]

    write_csv(out_dir / "real_workload_rtl_subset_gate.csv", gated)
    write_csv(out_dir / "real_workload_rtl_subset_summary.csv", summary)
    readme = """# Real Workload RTL Subset Ingest

This directory gates server RTL runs derived from real workload shapes.

Interpretation:

- `rtl_complete_clean`: completed without timeout and produced clean cycle markers.
- `rtl_partial_progress_clean`: timed out after producing clean cycle markers.
- `rtl_timeout_no_output`: timed out before producing usable cycle markers.
- `rtl_x_or_error`: unknown/X values or abnormal return code.

These rows are calibration evidence only. They are not direct paper-data rows
because the current scope is a bounded MAC-wrapper RTL subset, not full-chip
full-layer RTL timing with golden value comparison.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="results/flood_cycle_sim_v1/server_rtl_real_workload_v1/real_workload_rtl_subset_v1.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="results/flood_cycle_sim_v1/real_workload_rtl_subset_ingest",
    )
    args = parser.parse_args()
    ingest_subset(Path(args.input), Path(args.out_dir))


if __name__ == "__main__":
    main()
