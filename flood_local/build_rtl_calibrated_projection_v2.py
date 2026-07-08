#!/usr/bin/env python3
"""Build a P1-priority/P0-fallback RTL calibrated full-layer projection."""

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


def avg_cycles(row: dict[str, str]) -> float:
    run_count = as_int(row, "run_count")
    total = as_int(row, "total_cycles")
    return total / run_count if run_count > 0 else 0.0


def is_clean(row: dict[str, str]) -> bool:
    return (
        row.get("ready_for_calibration") == "yes"
        and row.get("expansion_status") in {"rtl_expansion_complete_clean", "rtl_expansion_partial_clean"}
        and as_int(row, "run_count") > 0
        and as_int(row, "total_cycles") > 0
        and as_int(row, "x_count") == 0
    )


def build_projection(p0_gate_csv: Path, p1_gate_csv: Path, plan_csv: Path, out_dir: Path) -> None:
    plan_by_case = {row.get("next_case_id", ""): row for row in read_rows(plan_csv)}
    candidates: dict[str, dict[str, str]] = {}
    for priority, rows in [("P0", read_rows(p0_gate_csv)), ("P1", read_rows(p1_gate_csv))]:
        for row in rows:
            if not is_clean(row):
                continue
            next_case = row.get("next_case_id", "")
            plan = plan_by_case.get(next_case, {})
            tile_count = as_int(plan, "full_layer_tile_count_estimate")
            if tile_count <= 0:
                continue
            source_case = row.get("source_case_id", "")
            candidate = {
                **row,
                "selected_priority": priority,
                "full_layer_tile_count_estimate": str(tile_count),
            }
            old = candidates.get(source_case)
            if old is None or (old.get("selected_priority") == "P0" and priority == "P1"):
                candidates[source_case] = candidate

    projected: list[dict[str, str]] = []
    for source_case, row in sorted(candidates.items()):
        avg = avg_cycles(row)
        tile_count = as_int(row, "full_layer_tile_count_estimate")
        projected.append(
            {
                "source_case_id": source_case,
                "selected_case_id": row.get("next_case_id", ""),
                "selected_priority": row.get("selected_priority", ""),
                "dataset": row.get("dataset", ""),
                "source_id": row.get("source_id", ""),
                "operator": row.get("operator", ""),
                "shape_args": row.get("shape_args", ""),
                "rtl_run_count": row.get("run_count", ""),
                "rtl_total_cycles": row.get("total_cycles", ""),
                "rtl_avg_cycles_per_marker": f"{avg:.2f}",
                "full_layer_tile_count_estimate": str(tile_count),
                "projected_mac_cycles": str(round(avg * tile_count)),
                "calibration_basis": "p1_large_tile_preferred" if row.get("selected_priority") == "P1" else "p0_safe_tile_fallback",
                "ready_for_direct_paper_data": "no",
                "paper_data_blocker": "projection_not_full_chip_and_no_independent_golden",
            }
        )

    p1_rows = sum(1 for row in projected if row["selected_priority"] == "P1")
    p0_rows = sum(1 for row in projected if row["selected_priority"] == "P0")
    summary = [
        {
            "projection_status": "pass" if projected else "missing_input",
            "projected_rows": str(len(projected)),
            "p1_selected_rows": str(p1_rows),
            "p0_fallback_rows": str(p0_rows),
            "direct_paper_ready_rows": "0",
            "paper_data_policy": "calibrated_projection_only_not_direct_paper_data",
            "main_blocker": "full-chip timing and independent software golden remain required",
        }
    ]
    write_csv(out_dir / "rtl_calibrated_projection_v2.csv", projected)
    write_csv(out_dir / "rtl_calibrated_projection_v2_summary.csv", summary)
    readme = """# RTL Calibrated Projection v2

This projection prefers clean P1 large-tile RTL evidence when available and
falls back to clean P0 safe-tile evidence otherwise.

It is more conservative than the original P0-only projection for rows where P1
evidence exists. It is still not direct paper data because it is not full-chip
timing and lacks independent software golden value checks.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p0-gate", default="results/flood_cycle_sim_v1/rtl_expansion_results_ingest/rtl_expansion_results_gate.csv")
    parser.add_argument("--p1-gate", default="results/flood_cycle_sim_v1/rtl_p1_expansion_results_ingest/rtl_expansion_results_gate.csv")
    parser.add_argument("--plan", default="results/flood_cycle_sim_v1/real_workload_rtl_expansion_plan/next_server_run_manifest.csv")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/rtl_calibrated_projection_v2")
    args = parser.parse_args()
    build_projection(Path(args.p0_gate), Path(args.p1_gate), Path(args.plan), Path(args.out_dir))


if __name__ == "__main__":
    main()
