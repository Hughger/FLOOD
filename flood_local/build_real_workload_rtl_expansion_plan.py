#!/usr/bin/env python3
"""Build the next server RTL run plan from real-workload subset evidence."""

from __future__ import annotations

import argparse
import csv
import math
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


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, default)))
    except (TypeError, ValueError):
        return default


def avg_cycle_per_run(row: dict[str, str]) -> str:
    run_count = as_int(row, "run_count")
    total_cycles = as_int(row, "total_cycles")
    if run_count <= 0 or total_cycles <= 0:
        return "NA"
    return f"{total_cycles / run_count:.2f}"


def conv_tile_count(shape_args: str) -> int:
    parts = [int(float(x)) for x in shape_args.split()]
    if len(parts) != 8:
        return 0
    _, h, w, cin, cout, _, stride, _ = parts
    tile_h = max(1, math.ceil(h / 16))
    tile_w = max(1, math.ceil(w / 16))
    cin_tiles = max(1, math.ceil(cin / 128))
    cout_tiles = max(1, math.ceil(cout / 64))
    stride_factor = max(1, stride)
    return tile_h * tile_w * cin_tiles * cout_tiles * stride_factor


def make_task(
    row: dict[str, str],
    suffix: str,
    priority: str,
    purpose: str,
    expected_policy: str,
    k: int,
    cout_blocks: int,
    cin_idx_total: int,
    res_cols: int,
    res_rows: int,
    timeout_s: int,
) -> dict[str, str]:
    return {
        "next_case_id": f"{row.get('case_id','case')}_{suffix}",
        "source_case_id": row.get("case_id", ""),
        "dataset": row.get("dataset", ""),
        "source_id": row.get("source_id", ""),
        "operator": row.get("operator", ""),
        "shape_args": row.get("shape_args", ""),
        "priority": priority,
        "purpose": purpose,
        "expected_policy": expected_policy,
        "k": str(k),
        "cout_blocks": str(cout_blocks),
        "group_size": row.get("group_size", "4") or "4",
        "group_num": row.get("group_num", "4") or "4",
        "cin_idx_total": str(cin_idx_total),
        "res_cols": str(res_cols),
        "res_rows": str(res_rows),
        "stride": row.get("stride", "1") or "1",
        "timeout_s": str(timeout_s),
        "previous_status": row.get("rtl_subset_status", ""),
        "previous_avg_cycle_per_run": avg_cycle_per_run(row),
        "full_layer_tile_count_estimate": str(conv_tile_count(row.get("shape_args", ""))),
        "paper_use_policy": "calibration_or_bringup_only_not_direct_paper_data",
    }


def build_plan(gate_csv: Path, out_dir: Path) -> None:
    rows = read_rows(gate_csv)
    tasks: list[dict[str, str]] = []
    for row in rows:
        operator = row.get("operator", "")
        status = row.get("rtl_subset_status", "")
        k = as_int(row, "k", 1)
        cout_blocks = as_int(row, "cout_blocks", 1)
        cin_idx_total = as_int(row, "cin_idx_total", 1)
        res_cols = as_int(row, "res_cols", 1)
        res_rows = as_int(row, "res_rows", 1)

        if operator == "conv" and status == "rtl_complete_clean":
            tasks.append(
                make_task(
                    row,
                    "repeat",
                    "P0",
                    "repeat completed tile to check reproducibility",
                    "should_complete_tile",
                    k,
                    cout_blocks,
                    cin_idx_total,
                    res_cols,
                    res_rows,
                    360,
                )
            )
        elif operator == "conv" and status == "rtl_partial_progress_clean":
            tasks.append(
                make_task(
                    row,
                    "safe_tile",
                    "P0",
                    "reduce large real layer to known-completable tile size",
                    "likely_complete_tile",
                    k,
                    min(cout_blocks, 2),
                    1,
                    1,
                    min(res_rows, 4),
                    360,
                )
            )
            tasks.append(
                make_task(
                    row,
                    "longer_partial",
                    "P1",
                    "rerun original larger tile with longer timeout to collect more markers",
                    "partial_or_complete_tile",
                    k,
                    cout_blocks,
                    cin_idx_total,
                    res_cols,
                    res_rows,
                    900,
                )
            )
        else:
            tasks.append(
                make_task(
                    row,
                    "bringup",
                    "P2",
                    "operator or kernel path produced no usable markers and needs separate bring-up",
                    "separate_testbench_bringup_required",
                    k,
                    max(1, min(cout_blocks, 2)),
                    max(1, min(cin_idx_total, 1)),
                    max(1, min(res_cols, 1)),
                    max(1, min(res_rows, 4)),
                    360,
                )
            )

    counts = {"P0": 0, "P1": 0, "P2": 0}
    for task in tasks:
        counts[task["priority"]] = counts.get(task["priority"], 0) + 1
    summary = [
        {
            "input_cases": str(len(rows)),
            "tasks": str(len(tasks)),
            "p0_tasks": str(counts.get("P0", 0)),
            "p1_tasks": str(counts.get("P1", 0)),
            "p2_tasks": str(counts.get("P2", 0)),
            "policy": "expand_clean_conv_tiles_first_and_quarantine_no_output_paths",
            "paper_data_policy": "not_direct_paper_data_until_full_layer_full_chip_value_timing",
        }
    ]

    write_csv(out_dir / "next_server_run_manifest.csv", tasks)
    write_csv(out_dir / "rtl_expansion_plan_summary.csv", summary)
    readme = """# Real Workload RTL Expansion Plan

This plan expands the first server RTL subset run without pretending it is
already paper data.

Priority meaning:

- P0: clean/reduced convolution tiles that should complete and improve timing calibration.
- P1: larger tiles that may still timeout but can collect more clean cycle markers.
- P2: no-output GEMM/1x1 paths that need separate testbench bring-up before use.

Rows remain calibration or bring-up only until full-layer/full-chip timing and
golden value checks are available.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gate-csv",
        default="results/flood_cycle_sim_v1/real_workload_rtl_subset_ingest/real_workload_rtl_subset_gate.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="results/flood_cycle_sim_v1/real_workload_rtl_expansion_plan",
    )
    args = parser.parse_args()
    build_plan(Path(args.gate_csv), Path(args.out_dir))


if __name__ == "__main__":
    main()
