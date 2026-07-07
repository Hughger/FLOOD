#!/usr/bin/env python3
"""Check whether RTL validation task manifests are ready for gate ingestion."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


PLACEHOLDER_PREFIXES = ("PATH_TO_", "TBD", "OPTIONAL_")
REQUIRED_MARKERS = {
    "FLOOD_CONFIG_CYCLES",
    "FLOOD_ACTIVATION_DMA_CYCLES",
    "FLOOD_WEIGHT_DMA_CYCLES",
    "FLOOD_MAC_CYCLES",
    "FLOOD_OUTPUT_DMA_CYCLES",
    "FLOOD_SYSTEM_TOTAL_CYCLES",
    "FLOOD_RTL_STATUS",
}


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


def is_placeholder(value: str) -> bool:
    value = str(value).strip()
    return not value or any(value.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def check_manifests(task_csv: Path, system_csv: Path, value_csv: Path, out_dir: Path) -> None:
    tasks = read_rows(task_csv)
    system_rows = read_rows(system_csv)
    value_rows = read_rows(value_csv)
    system_ids = {row.get("calibration_id", "") for row in system_rows}
    value_ids = {row.get("workload_id", "") for row in value_rows}
    rows: list[dict[str, str]] = []

    for task in tasks:
        task_id = task.get("task_id", "")
        issues: list[str] = []
        markers = {item for item in task.get("required_log_markers", "").split(";") if item}
        missing_markers = sorted(REQUIRED_MARKERS - markers)
        if missing_markers:
            issues.append("missing_required_markers=" + ",".join(missing_markers))
        if task_id not in system_ids:
            issues.append("missing_system_manifest_row")
        if task_id not in value_ids:
            issues.append("missing_value_manifest_row")
        for field in ["rtl_log_file", "golden_values_file", "rtl_values_file"]:
            value = task.get(field, "")
            if is_placeholder(value):
                issues.append(f"{field}_placeholder")
            elif not Path(value).exists():
                issues.append(f"{field}_missing_file")
        status = "ready_for_gate_ingestion" if not issues else "not_ready"
        rows.append(
            {
                "task_id": task_id,
                "priority": task.get("priority", ""),
                "workload_id": task.get("workload_id", ""),
                "status": status,
                "issues": ";".join(issues),
            }
        )

    write_csv(out_dir / "rtl_task_manifest_check.csv", rows)
    ready = sum(1 for row in rows if row["status"] == "ready_for_gate_ingestion")
    not_ready = len(rows) - ready
    placeholder_rows = sum(1 for row in rows if "placeholder" in row.get("issues", ""))
    summary = [
        {
            "tasks": str(len(rows)),
            "ready_for_gate_ingestion": str(ready),
            "not_ready": str(not_ready),
            "placeholder_rows": str(placeholder_rows),
            "policy": "Only ready_for_gate_ingestion tasks may be fed to system/value/final gates.",
        }
    ]
    write_csv(out_dir / "rtl_task_manifest_check_summary.csv", summary)
    readme = """# FLOOD RTL Task Manifest Check

This report checks whether RTL task manifests are ready to feed into the
system/value/final gates.

Draft manifests are expected to fail because they contain `PATH_TO_*`
placeholders. After real RTL logs and output files are collected, rerun this
check; only `ready_for_gate_ingestion` tasks should enter paper-data gates.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-csv", required=True)
    parser.add_argument("--system-manifest", required=True)
    parser.add_argument("--value-manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    check_manifests(Path(args.task_csv), Path(args.system_manifest), Path(args.value_manifest), Path(args.out_dir))


if __name__ == "__main__":
    main()
