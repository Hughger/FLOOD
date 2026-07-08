#!/usr/bin/env python3
"""Gate server RTL expansion results and reparse cycle markers from logs."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


DONE_PATTERNS = [
    re.compile(r"Done interrupt after\s+(\d+)\s+cycles", re.IGNORECASE),
    re.compile(r"cycles\s*=\s*(\d+)", re.IGNORECASE),
    re.compile(r"cycle_count\s*=\s*(\d+)", re.IGNORECASE),
]


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


def parse_cycles(text: str) -> list[int]:
    for pattern in DONE_PATTERNS:
        cycles = [int(x) for x in pattern.findall(text)]
        if cycles:
            return cycles
    return []


def classify(row: dict[str, str]) -> str:
    rc = as_int(row, "rc")
    run_count = as_int(row, "run_count")
    x_count = as_int(row, "x_count")
    timeout = (row.get("timeout", "") or "").strip().lower()
    if x_count > 0 or rc not in {0, 124}:
        return "rtl_expansion_x_or_error"
    if rc == 0 and run_count > 0 and timeout == "no":
        return "rtl_expansion_complete_clean"
    if timeout == "yes" and run_count > 0:
        return "rtl_expansion_partial_clean"
    if rc == 0 and run_count == 0:
        return "rtl_expansion_completed_without_cycle_marker"
    return "rtl_expansion_timeout_no_output"


def ingest_results(raw_csv: Path, log_root: Path, out_dir: Path) -> None:
    rows = read_rows(raw_csv)
    gated: list[dict[str, str]] = []
    for row in rows:
        log_rel = row.get("log", "")
        log_path = log_root / log_rel
        if not log_path.exists():
            log_path = log_root / Path(log_rel).name
        text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        cycles = parse_cycles(text)
        if cycles:
            row = {
                **row,
                "run_count": str(len(cycles)),
                "cycle_list": ";".join(str(x) for x in cycles),
                "total_cycles": str(sum(cycles)),
            }
        status = classify(row)
        gated.append(
            {
                **row,
                "expansion_status": status,
                "ready_for_calibration": "yes"
                if status in {"rtl_expansion_complete_clean", "rtl_expansion_partial_clean"}
                else "no",
                "ready_for_direct_paper_data": "no",
                "paper_data_blocker": "p0_tile_level_rtl_not_full_layer_full_chip_value_timing",
            }
        )

    counts: dict[str, int] = {}
    for row in gated:
        counts[row["expansion_status"]] = counts.get(row["expansion_status"], 0) + 1
    calibration_ready = counts.get("rtl_expansion_complete_clean", 0) + counts.get("rtl_expansion_partial_clean", 0)
    summary = [
        {
            "ingest_status": "pass" if rows else "missing_input",
            "total_cases": str(len(rows)),
            "complete_clean_cases": str(counts.get("rtl_expansion_complete_clean", 0)),
            "partial_clean_cases": str(counts.get("rtl_expansion_partial_clean", 0)),
            "completed_without_cycle_marker_cases": str(counts.get("rtl_expansion_completed_without_cycle_marker", 0)),
            "timeout_no_output_cases": str(counts.get("rtl_expansion_timeout_no_output", 0)),
            "x_or_error_cases": str(counts.get("rtl_expansion_x_or_error", 0)),
            "calibration_ready_cases": str(calibration_ready),
            "direct_paper_ready_cases": "0",
            "paper_data_policy": "calibration_only_not_direct_paper_data",
            "main_blocker": "tile-level RTL evidence without full-layer/full-chip value and timing",
        }
    ]
    write_csv(out_dir / "rtl_expansion_results_gate.csv", gated)
    write_csv(out_dir / "rtl_expansion_results_summary.csv", summary)
    readme = """# RTL Expansion Results

These rows are parsed from the second server-side P0 expansion run.

They are useful as calibration evidence when they have clean cycle markers, but
they are still not direct paper data because they are tile-level MAC-wrapper RTL
runs rather than full-layer/full-chip timing with golden value checks.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-csv",
        default="results/flood_cycle_sim_v1/server_rtl_real_workload_v2/p0_expansion_results.csv",
    )
    parser.add_argument(
        "--log-root",
        default="results/flood_cycle_sim_v1/server_rtl_real_workload_v2/logs",
    )
    parser.add_argument(
        "--out-dir",
        default="results/flood_cycle_sim_v1/rtl_expansion_results_ingest",
    )
    args = parser.parse_args()
    ingest_results(Path(args.raw_csv), Path(args.log_root), Path(args.out_dir))


if __name__ == "__main__":
    main()
