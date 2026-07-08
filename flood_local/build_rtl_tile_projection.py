#!/usr/bin/env python3
"""Build full-layer MAC projections from clean RTL tile expansion results."""

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


def build_projection(expansion_gate_csv: Path, expansion_plan_csv: Path, out_dir: Path) -> None:
    gate_rows = read_rows(expansion_gate_csv)
    plan_by_case = {row.get("next_case_id", ""): row for row in read_rows(expansion_plan_csv)}
    projected: list[dict[str, str]] = []

    for row in gate_rows:
        if row.get("ready_for_calibration") != "yes":
            continue
        run_count = as_int(row, "run_count")
        total_cycles = as_int(row, "total_cycles")
        if run_count <= 0 or total_cycles <= 0:
            continue
        plan = plan_by_case.get(row.get("next_case_id", ""), {})
        tile_count = as_int(plan, "full_layer_tile_count_estimate")
        if tile_count <= 0:
            continue
        avg_cycles = total_cycles / run_count
        projected_cycles = round(avg_cycles * tile_count)
        projected.append(
            {
                "next_case_id": row.get("next_case_id", ""),
                "source_case_id": row.get("source_case_id", ""),
                "dataset": row.get("dataset", ""),
                "source_id": row.get("source_id", ""),
                "operator": row.get("operator", ""),
                "shape_args": row.get("shape_args", ""),
                "priority": row.get("priority", ""),
                "rtl_tile_run_count": str(run_count),
                "rtl_tile_total_cycles": str(total_cycles),
                "rtl_avg_cycles_per_tile_run": f"{avg_cycles:.2f}",
                "full_layer_tile_count_estimate": str(tile_count),
                "rtl_tile_projected_mac_cycles": str(projected_cycles),
                "projection_scope": "mac_wrapper_tile_calibrated_full_layer_projection",
                "calibration_status": row.get("expansion_status", ""),
                "ready_for_direct_paper_data": "no",
                "paper_data_blocker": "projection_not_full_chip_and_no_golden_value_check",
                "paper_use_policy": "calibration_projection_only",
            }
        )

    direct_ready = sum(1 for row in projected if row.get("ready_for_direct_paper_data") == "yes")
    summary = [
        {
            "projection_status": "pass" if projected else "missing_input",
            "projected_rows": str(len(projected)),
            "direct_paper_ready_rows": str(direct_ready),
            "calibration_projection_rows": str(len(projected) - direct_ready),
            "paper_data_policy": "not_direct_paper_data_until_full_chip_value_timing",
            "main_blocker": "full-chip timing and golden value checks are still required",
        }
    ]

    write_csv(out_dir / "rtl_tile_full_layer_projection.csv", projected)
    write_csv(out_dir / "rtl_tile_projection_summary.csv", summary)
    readme = """# RTL Tile-Calibrated Full-Layer Projection

This table uses clean server RTL tile runs to estimate full-layer MAC-wrapper
cycles by multiplying average tile-run cycles by estimated full-layer tile
count.

This is stronger than a pure analytic projection, but it is still not direct
paper data. It does not include full-chip CPU/DMA/control timing and it does
not prove numerical agreement against golden outputs.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expansion-gate",
        default="results/flood_cycle_sim_v1/rtl_expansion_results_ingest/rtl_expansion_results_gate.csv",
    )
    parser.add_argument(
        "--expansion-plan",
        default="results/flood_cycle_sim_v1/real_workload_rtl_expansion_plan/next_server_run_manifest.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="results/flood_cycle_sim_v1/rtl_tile_projection",
    )
    args = parser.parse_args()
    build_projection(Path(args.expansion_gate), Path(args.expansion_plan), Path(args.out_dir))


if __name__ == "__main__":
    main()
