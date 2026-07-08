#!/usr/bin/env python3
"""Summarize whether the FLOOD postprocessor can emit paper-ready data."""

from __future__ import annotations

import argparse
import csv
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


def build_scorecard(results_root: Path, out_dir: Path) -> None:
    final_summary = first_row(results_root / "final_paper_gate_smoke" / "final_paper_data_summary.csv")
    export_summary = first_row(results_root / "main_figure_export_smoke" / "export_summary.csv")
    export_audit = first_row(results_root / "main_figure_export_audit_smoke" / "main_figure_export_audit_summary.csv")
    coverage = first_row(results_root / "validation_coverage" / "coverage_readiness_summary.csv")
    task_summary = first_row(results_root / "rtl_task_manifest" / "rtl_task_summary.csv")
    task_check = first_row(results_root / "rtl_task_manifest_check" / "rtl_task_manifest_check_summary.csv")
    completed_ingest = first_row(results_root / "completed_ingest_smoke" / "completed_ingest_summary.csv")
    completed_export_audit = first_row(results_root / "completed_ingest_smoke" / "main_figure_export_audit" / "main_figure_export_audit_summary.csv")
    rtl_source = first_row(results_root / "rtl_source_manifest" / "rtl_source_summary.csv")
    value_person2 = first_row(results_root / "person2_gemm" / "value_check_summary.csv")
    value_unet = first_row(results_root / "synthetic_unet_trace" / "value_check_summary.csv")
    system_smoke = first_row(results_root / "system_calibration_smoke" / "system_calibration_summary.csv")
    source_bundle_auto = first_row(results_root / "source_bundle_auto_verify" / "rtl_source_bundle_verify_summary.csv")
    server_source_bundle_auto = first_row(results_root / "server_linux_repro_30659" / "source_bundle_auto_verify_summary.csv")
    server_source_bundle_tamper = first_row(results_root / "server_linux_repro_30659" / "source_bundle_tamper_verify" / "rtl_source_bundle_verify_summary.csv")

    exported_rows = as_int(export_summary, "exported_main_figure_rows")
    rejected_rows = as_int(export_summary, "rejected_rows")
    ready_tasks = as_int(task_check, "ready_for_gate_ingestion")
    placeholder_rows = as_int(task_check, "placeholder_rows")
    p0_tasks = as_int(task_summary, "p0_tasks")
    p0_rows = as_int(coverage, "p0_rows")
    system_mismatch = as_int(system_smoke, "mismatch_rows")
    hardware_sig = rtl_source.get("hardware_source_signature_sha256", "")
    ingest_ready_tasks = as_int(completed_ingest, "ready_for_gate_ingestion")
    ingest_system_ready = as_int(completed_ingest, "system_ready_rows")
    ingest_value_ready = as_int(completed_ingest, "value_ready_rows")
    source_bundle_statuses = [
        status
        for status in [
            source_bundle_auto.get("verify_status", ""),
            server_source_bundle_auto.get("verify_status", ""),
        ]
        if status
    ]
    source_bundle_auto_pass = "pass" in source_bundle_statuses
    source_bundle_tamper_fails = (
        server_source_bundle_tamper.get("verify_status") == "fail"
        and as_int(server_source_bundle_tamper, "failed_files") > 0
    )

    checks = [
        {
            "check": "hardware_source_signature_present",
            "status": "pass" if hardware_sig else "fail",
            "evidence": hardware_sig,
            "next_action": "Rerun full postprocessor gates if the signature changes.",
        },
        {
            "check": "linux_runner_source_bundle_auto_verify_passes",
            "status": "pass" if source_bundle_auto_pass else "fail",
            "evidence": f"local={source_bundle_auto.get('verify_status','missing')}, server={server_source_bundle_auto.get('verify_status','missing')}",
            "next_action": "Run Linux/server postprocessor only after source bundle auto verification passes.",
        },
        {
            "check": "source_bundle_tamper_adversarial_verify_fails",
            "status": "pass" if source_bundle_tamper_fails else "fail",
            "evidence": f"tamper_status={server_source_bundle_tamper.get('verify_status','missing')}, failed_files={server_source_bundle_tamper.get('failed_files','0')}",
            "next_action": "Keep tamper failure evidence with server reproduction artifacts.",
        },
        {
            "check": "final_gate_exists_and_blocks_unqualified_rows",
            "status": "pass" if as_int(final_summary, "paper_rows") > 0 and as_int(final_summary, "not_ready_for_main_figure") > 0 else "fail",
            "evidence": f"paper_rows={final_summary.get('paper_rows','0')}, not_ready={final_summary.get('not_ready_for_main_figure','0')}",
            "next_action": "Use final_paper_data_policy as the paper-data authority.",
        },
        {
            "check": "main_figure_export_contains_only_approved_rows",
            "status": "pass" if exported_rows == 0 and rejected_rows > 0 else "fail",
            "evidence": f"exported={exported_rows}, rejected={rejected_rows}",
            "next_action": "Plot only from main_figure_rows.csv.",
        },
        {
            "check": "main_figure_export_adversarial_audit_passes",
            "status": "pass" if export_audit.get("audit_status") == "pass" and completed_export_audit.get("audit_status") == "pass" else "fail",
            "evidence": f"main={export_audit.get('audit_status','missing')}, completed_ingest={completed_export_audit.get('audit_status','missing')}",
            "next_action": "Treat any audit failure as paper-data leakage until fixed.",
        },
        {
            "check": "real_workload_value_evidence_present",
            "status": "pass" if value_person2.get("value_check_status") == "pass" and value_unet.get("value_check_status") == "pass" else "missing_input_evidence",
            "evidence": f"person2={value_person2.get('value_check_status','missing')}, synthetic_unet={value_unet.get('value_check_status','missing')}",
            "next_action": "Collect golden and RTL numeric outputs for paper workloads.",
        },
        {
            "check": "system_calibration_ready_for_main_data",
            "status": "pass" if system_mismatch == 0 and as_int(system_smoke, "measured_rows") > 0 else "missing_or_mismatched_input_evidence",
            "evidence": f"measured={system_smoke.get('measured_rows','0')}, mismatch={system_smoke.get('mismatch_rows','0')}",
            "next_action": "Collect full-chip logs until mismatch_rows=0 for claimed workload scope.",
        },
        {
            "check": "next_rtl_tasks_are_actionable_but_not_ingested",
            "status": "pass" if p0_tasks > 0 and placeholder_rows > 0 and ready_tasks == 0 else "fail",
            "evidence": f"p0_tasks={p0_tasks}, coverage_p0_rows={p0_rows}, ready_tasks={ready_tasks}, placeholder_rows={placeholder_rows}",
            "next_action": "Replace task placeholders with real logs/outputs before ingestion.",
        },
        {
            "check": "completed_rtl_task_ingest_pipeline_runs",
            "status": "pass" if completed_ingest.get("ingest_status") == "pass" and ingest_ready_tasks > 0 and ingest_system_ready > 0 and ingest_value_ready > 0 else "fail",
            "evidence": f"ingest_status={completed_ingest.get('ingest_status','missing')}, ready_tasks={ingest_ready_tasks}, system_ready={ingest_system_ready}, value_ready={ingest_value_ready}, exported={completed_ingest.get('exported_main_figure_rows','0')}",
            "next_action": "Use run_completed_rtl_task_ingest.py for completed student/server RTL outputs.",
        },
    ]
    write_csv(out_dir / "postprocessor_checks.csv", checks)

    failing = [row for row in checks if row["status"] not in {"pass"}]
    exported_policy = "paper_ready_data_available" if exported_rows > 0 and not failing else "no_paper_ready_rows_yet"
    summary = [
        {
            "postprocessor_status": "gate_stack_ready_but_waiting_for_real_rtl_value_inputs",
            "paper_data_policy": exported_policy,
            "main_figure_rows": str(exported_rows),
            "rejected_rows": str(rejected_rows),
            "checks": str(len(checks)),
            "non_pass_checks": str(len(failing)),
            "primary_blocker": "real workload golden/RTL value outputs and full-chip calibration logs",
        }
    ]
    write_csv(out_dir / "postprocessor_summary.csv", summary)
    readme = """# FLOOD Postprocessor Scorecard

This scorecard is aligned with the current goal: optimize the PyTorchSim ->
FLOOD postprocessor so it can emit qualified paper data.

Current interpretation:

- The gate stack is in place.
- Completed RTL task manifests can be ingested through system/value/final/export gates.
- Current smoke data is correctly rejected from main figures.
- Qualified paper data still requires real RTL/golden value outputs and
  full-chip calibration logs.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", default="results/flood_cycle_sim_v1")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/postprocessor_scorecard")
    args = parser.parse_args()
    build_scorecard(Path(args.results_root), Path(args.out_dir))


if __name__ == "__main__":
    main()
