#!/usr/bin/env python3
"""Ingest completed RTL task results into FLOOD paper-data gates."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def first_row(path: Path) -> dict[str, str]:
    rows = read_rows(path)
    return rows[0] if rows else {}


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


def run_step(name: str, cmd: list[str], status_rows: list[dict[str, str]]) -> None:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    message = (proc.stderr or proc.stdout).strip().replace("\n", " ")[:700]
    status_rows.append(
        {
            "step": name,
            "returncode": str(proc.returncode),
            "status": "pass" if proc.returncode == 0 else "fail",
            "command": " ".join(cmd),
            "message": message,
        }
    )
    if proc.returncode != 0:
        raise SystemExit(f"{name} failed. See ingest_run_status.csv.")


def validate_ready_tasks(check_dir: Path) -> tuple[int, int]:
    summary = first_row(check_dir / "rtl_task_manifest_check_summary.csv")
    ready = as_int(summary, "ready_for_gate_ingestion")
    tasks = as_int(summary, "tasks")
    if tasks <= 0:
        raise SystemExit("No RTL tasks were checked.")
    if ready <= 0:
        raise SystemExit("No RTL task is ready_for_gate_ingestion.")
    return tasks, ready


def build_ingest(
    task_csv: Path,
    system_manifest: Path,
    value_manifest: Path,
    paper_gate_manifest: Path,
    workload_gate: Path,
    rtl_source_summary: Path,
    out_root: Path,
) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    status_rows: list[dict[str, str]] = []
    try:
        manifest_check = out_root / "manifest_check"
        system_batch = out_root / "system_batch"
        value_batch = out_root / "value_batch"
        final_gate = out_root / "final_gate"
        main_export = out_root / "main_figure_export"

        run_step(
            "manifest_check",
            [
                sys.executable,
                str(Path("flood_local") / "check_rtl_task_manifest.py"),
                "--task-csv",
                str(task_csv),
                "--system-manifest",
                str(system_manifest),
                "--value-manifest",
                str(value_manifest),
                "--out-dir",
                str(manifest_check),
            ],
            status_rows,
        )
        checked_tasks, ready_tasks = validate_ready_tasks(manifest_check)
        status_rows.append(
            {
                "step": "manifest_ready_gate",
                "returncode": "0",
                "status": "pass",
                "command": "",
                "message": f"checked_tasks={checked_tasks}, ready_for_gate_ingestion={ready_tasks}",
            }
        )

        run_step(
            "system_calibration_batch",
            [
                sys.executable,
                str(Path("flood_local") / "run_system_calibration_batch.py"),
                "--manifest",
                str(system_manifest),
                "--out-root",
                str(system_batch),
            ],
            status_rows,
        )
        run_step(
            "value_check_batch",
            [
                sys.executable,
                str(Path("flood_local") / "run_value_check_batch.py"),
                "--manifest",
                str(value_manifest),
                "--out-root",
                str(value_batch),
            ],
            status_rows,
        )
        run_step(
            "final_paper_data_gate",
            [
                sys.executable,
                str(Path("flood_local") / "build_paper_data_gate.py"),
                "--manifest",
                str(paper_gate_manifest),
                "--workload-gate",
                str(workload_gate),
                "--value-gate",
                str(value_batch / "value_readiness_summary.csv"),
                "--system-gate",
                str(system_batch / "calibration_readiness_summary.csv"),
                "--rtl-source-summary",
                str(rtl_source_summary),
                "--out-dir",
                str(final_gate),
            ],
            status_rows,
        )
        run_step(
            "main_figure_export",
            [
                sys.executable,
                str(Path("flood_local") / "export_main_figure_package.py"),
                "--final-gate",
                str(final_gate / "final_paper_data_gate.csv"),
                "--out-dir",
                str(main_export),
            ],
            status_rows,
        )
    finally:
        write_csv(out_root / "ingest_run_status.csv", status_rows)

    final_summary = first_row(out_root / "final_gate" / "final_paper_data_summary.csv")
    export_summary = first_row(out_root / "main_figure_export" / "export_summary.csv")
    check_summary = first_row(out_root / "manifest_check" / "rtl_task_manifest_check_summary.csv")
    system_ready_rows = read_rows(out_root / "system_batch" / "calibration_readiness_summary.csv")
    value_ready_rows = read_rows(out_root / "value_batch" / "value_readiness_summary.csv")
    system_ready = sum(1 for row in system_ready_rows if row.get("paper_system_timing_policy") == "ready_for_main_figure_system_timing")
    value_ready = sum(1 for row in value_ready_rows if row.get("main_value_ready_policy") == "ready_for_main_figure_value")
    summary = [
        {
            "ingest_status": "pass",
            "checked_tasks": check_summary.get("tasks", "0"),
            "ready_for_gate_ingestion": check_summary.get("ready_for_gate_ingestion", "0"),
            "system_ready_rows": str(system_ready),
            "value_ready_rows": str(value_ready),
            "final_ready_rows": final_summary.get("ready_for_main_figure", "0"),
            "final_not_ready_rows": final_summary.get("not_ready_for_main_figure", "0"),
            "exported_main_figure_rows": export_summary.get("exported_main_figure_rows", "0"),
            "policy": "Completed RTL task outputs must pass this ingest before plotting.",
        }
    ]
    write_csv(out_root / "completed_ingest_summary.csv", summary)
    readme = f"""# FLOOD Completed RTL Task Ingest

Inputs:

- task CSV: `{task_csv}`
- system manifest: `{system_manifest}`
- value manifest: `{value_manifest}`
- paper gate manifest: `{paper_gate_manifest}`

This directory is the postprocessor path for finished student/server RTL runs.
It checks that completed task files are real, parses full-chip timing logs,
checks numeric outputs, merges evidence into the final paper gate, and exports
only rows approved for main figures.

Generated files:

- `ingest_run_status.csv`: command status for each stage.
- `manifest_check/`: path and required-marker readiness check.
- `system_batch/`: full-chip/system timing gate.
- `value_batch/`: golden-vs-RTL numeric gate.
- `final_gate/`: workload/value/system merged paper gate.
- `main_figure_export/`: CSVs allowed for plotting.
"""
    (out_root / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-csv", required=True)
    parser.add_argument("--system-manifest", required=True)
    parser.add_argument("--value-manifest", required=True)
    parser.add_argument("--paper-gate-manifest", required=True)
    parser.add_argument("--workload-gate", required=True)
    parser.add_argument("--rtl-source-summary", required=True)
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    build_ingest(
        Path(args.task_csv),
        Path(args.system_manifest),
        Path(args.value_manifest),
        Path(args.paper_gate_manifest),
        Path(args.workload_gate),
        Path(args.rtl_source_summary),
        Path(args.out_root),
    )


if __name__ == "__main__":
    main()
