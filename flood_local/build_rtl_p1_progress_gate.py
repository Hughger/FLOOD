#!/usr/bin/env python3
"""Summarize P1 large-tile RTL progress and isolate risky samples."""

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


def build_gate(p1_gate_csv: Path, out_dir: Path) -> None:
    rows = read_rows(p1_gate_csv)
    detail: list[dict[str, str]] = []
    for row in rows:
        clean_progress = row.get("expansion_status") in {"rtl_expansion_complete_clean", "rtl_expansion_partial_clean"}
        isolated = row.get("expansion_status") == "rtl_expansion_x_or_error" or as_int(row, "x_count") > 0
        detail.append(
            {
                **row,
                "p1_progress_policy": "clean_large_tile_progress" if clean_progress else "isolated_not_for_calibration",
                "x_isolation_policy": "isolated_x_or_error" if isolated else "no_x_detected",
                "ready_for_direct_paper_data": "no",
                "paper_data_blocker": "p1_partial_or_x_isolated_not_full_layer_full_chip",
            }
        )

    clean = sum(1 for row in detail if row["p1_progress_policy"] == "clean_large_tile_progress")
    isolated = sum(1 for row in detail if row["x_isolation_policy"] == "isolated_x_or_error")
    total_markers = sum(as_int(row, "run_count") for row in detail if row["p1_progress_policy"] == "clean_large_tile_progress")
    summary = [
        {
            "p1_progress_status": "partial_pass_with_isolated_x_cases"
            if clean > 0 and isolated > 0
            else "pass" if clean > 0 else "missing_or_failed",
            "cases": str(len(detail)),
            "clean_progress_cases": str(clean),
            "isolated_x_or_error_cases": str(isolated),
            "clean_cycle_markers": str(total_markers),
            "direct_paper_ready_cases": "0",
            "paper_data_policy": "large_tile_progress_only_not_direct_paper_data",
        }
    ]
    write_csv(out_dir / "rtl_p1_progress_detail.csv", detail)
    write_csv(out_dir / "rtl_p1_progress_summary.csv", summary)
    readme = """# RTL P1 Large-Tile Progress Gate

P1 runs use larger real-workload tile settings than the P0 safe tiles. They are
allowed to timeout, but any clean done-cycle markers are useful calibration
evidence. Samples with X/unknown output are explicitly isolated.

This is progress evidence only, not direct paper data.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--p1-gate",
        default="results/flood_cycle_sim_v1/rtl_p1_expansion_results_ingest/rtl_expansion_results_gate.csv",
    )
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/rtl_p1_progress_gate")
    args = parser.parse_args()
    build_gate(Path(args.p1_gate), Path(args.out_dir))


if __name__ == "__main__":
    main()
