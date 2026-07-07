#!/usr/bin/env python3
"""Convert validation coverage priorities into executable RTL task manifests."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


REQUIRED_MARKERS = [
    "FLOOD_CONFIG_CYCLES",
    "FLOOD_ACTIVATION_DMA_CYCLES",
    "FLOOD_WEIGHT_DMA_CYCLES",
    "FLOOD_MAC_CYCLES",
    "FLOOD_OUTPUT_DMA_CYCLES",
    "FLOOD_SYSTEM_TOTAL_CYCLES",
    "FLOOD_RTL_STATUS",
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


def build_task_manifests(priority_csv: Path, out_dir: Path, limit: int) -> None:
    rows = read_rows(priority_csv)
    selected = rows[:limit] if limit > 0 else rows
    task_rows: list[dict[str, str]] = []
    system_manifest: list[dict[str, str]] = []
    value_manifest: list[dict[str, str]] = []
    log_map_rows: list[dict[str, str]] = []

    for idx, row in enumerate(selected, start=1):
        task_id = f"rtl_task_{idx:03d}_{row.get('workload_id', 'unknown')}"
        out_subdir = task_id
        rtl_log_placeholder = f"PATH_TO_RTL_LOGS/{task_id}.log"
        golden_placeholder = f"PATH_TO_GOLDEN_OUTPUTS/{task_id}.txt"
        rtl_values_placeholder = f"PATH_TO_RTL_OUTPUTS/{task_id}.txt"
        template_placeholder = f"PATH_TO_SYSTEM_TEMPLATES/{task_id}_system_template.csv"
        log_map_placeholder = f"PATH_TO_LOG_MAPS/{task_id}_log_map.csv"

        task_rows.append(
            {
                "task_id": task_id,
                "priority": row.get("next_validation_priority", ""),
                "result_dir": row.get("result_dir", ""),
                "workload_id": row.get("workload_id", ""),
                "operator": row.get("operator", ""),
                "source_stage": row.get("source_stage", ""),
                "shape_args": row.get("shape_args", ""),
                "k": row.get("k", ""),
                "cout": row.get("cout", ""),
                "cin_idx_total": row.get("cin_idx_total", ""),
                "spatial_points": row.get("spatial_points", ""),
                "projected_total_cycles": row.get("total_cycles", ""),
                "confidence_grade": row.get("confidence_grade", ""),
                "required_log_markers": ";".join(REQUIRED_MARKERS),
                "rtl_log_file": rtl_log_placeholder,
                "golden_values_file": golden_placeholder,
                "rtl_values_file": rtl_values_placeholder,
                "acceptance_gate": "system mismatch_rows=0 and value_check_status=pass",
                "blockers_from_coverage": row.get("blockers", ""),
            }
        )
        system_manifest.append(
            {
                "calibration_id": task_id,
                "template_csv": template_placeholder,
                "log_map_csv": log_map_placeholder,
                "out_subdir": out_subdir,
                "system_model_csv": "",
                "owner": "TBD",
                "notes": "Replace placeholders after RTL/testbench run; requires explicit FLOOD_* cycle markers.",
            }
        )
        value_manifest.append(
            {
                "workload_id": task_id,
                "golden_values": golden_placeholder,
                "rtl_values": rtl_values_placeholder,
                "out_subdir": out_subdir,
                "rtol": "0.0",
                "atol": "0.0",
                "owner": "TBD",
                "notes": "Replace placeholders after collecting golden and RTL numeric outputs.",
            }
        )
        log_map_rows.append(
            {
                "workload_id": row.get("workload_id", ""),
                "log_file": rtl_log_placeholder,
                "task_id": task_id,
            }
        )

    write_csv(out_dir / "rtl_validation_tasks.csv", task_rows)
    write_csv(out_dir / "system_calibration_manifest_draft.csv", system_manifest)
    write_csv(out_dir / "value_check_manifest_draft.csv", value_manifest)
    write_csv(out_dir / "rtl_log_map_draft.csv", log_map_rows)
    p0 = sum(1 for row in task_rows if row.get("priority", "").startswith("P0"))
    p1 = sum(1 for row in task_rows if row.get("priority", "").startswith("P1"))
    summary = [
        {
            "source_priority_csv": str(priority_csv),
            "tasks": str(len(task_rows)),
            "p0_tasks": str(p0),
            "p1_tasks": str(p1),
            "limit": str(limit),
            "policy": "Run these tasks in RTL/testbench, then replace placeholders and feed generated manifests to system/value/final gates.",
        }
    ]
    write_csv(out_dir / "rtl_task_summary.csv", summary)
    readme = """# FLOOD RTL Validation Task Manifest

This directory turns validation coverage priorities into executable task lists.

Generated files:

- `rtl_validation_tasks.csv`: task list for RTL/testbench execution.
- `system_calibration_manifest_draft.csv`: draft input for `run_system_calibration_batch.py`.
- `value_check_manifest_draft.csv`: draft input for `run_value_check_batch.py`.
- `rtl_log_map_draft.csv`: draft mapping from workload_id to RTL log path.
- `rtl_task_summary.csv`: task counts.

The generated paths are placeholders. Replace them with real RTL log and output
files after running the tasks.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--priority-csv", default="results/flood_cycle_sim_v1/validation_coverage/next_rtl_validation_priority.csv")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/rtl_task_manifest")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    build_task_manifests(Path(args.priority_csv), Path(args.out_dir), args.limit)


if __name__ == "__main__":
    main()
