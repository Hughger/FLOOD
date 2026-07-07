#!/usr/bin/env python3
"""Build a conservative readiness audit for the FLOOD cycle simulator."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


PASS = "pass"
PARTIAL = "partial"
MISSING = "missing"
BLOCKED = "blocked_by_evidence"


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def first_row(path: Path) -> dict[str, str]:
    rows = read_rows(path)
    return rows[0] if rows else {}


def as_int(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, default)))
    except (TypeError, ValueError):
        return default


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def add(
    rows: list[dict[str, str]],
    area: str,
    requirement: str,
    status: str,
    evidence: str,
    blocker: str,
    next_action: str,
) -> None:
    rows.append(
        {
            "area": area,
            "requirement": requirement,
            "status": status,
            "evidence": evidence,
            "blocker": blocker,
            "next_action": next_action,
        }
    )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = {PASS: 0, PARTIAL: 0, MISSING: 0, BLOCKED: 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def build_report(results_root: Path, out_dir: Path) -> None:
    rows: list[dict[str, str]] = []

    rtl_summary_path = results_root / "rtl_validation" / "rtl_validation_summary.csv"
    rtl = first_row(rtl_summary_path)
    rtl_clean = as_int(rtl, "rtl_clean_cases")
    passed = as_int(rtl, "passed_cases")
    failed = as_int(rtl, "failed_cases")
    max_err = as_float(rtl, "max_abs_cycle_error")
    blocked = as_int(rtl, "direct_blocked_cases")

    if rtl_clean > 0 and passed == rtl_clean and failed == 0 and max_err == 0:
        add(
            rows,
            "base_mac_timing",
            "Base FLOOD MAC clean RTL cycle intervals are reproduced exactly.",
            PASS,
            f"{rtl_summary_path}: {passed}/{rtl_clean} pass, max_abs_cycle_error={max_err:g}",
            "",
            "Keep these rows as the current highest-confidence timing anchor.",
        )
    else:
        add(
            rows,
            "base_mac_timing",
            "Base FLOOD MAC clean RTL cycle intervals are reproduced exactly.",
            MISSING,
            f"{rtl_summary_path}",
            "No all-pass direct RTL-clean timing anchor.",
            "Fix direct RTL-clean mismatches before running paper-scale workloads.",
        )

    rtl_source_summary_path = results_root / "rtl_source_manifest" / "rtl_source_summary.csv"
    rtl_source_summary = first_row(rtl_source_summary_path)
    source_files = as_int(rtl_source_summary, "source_files")
    missing_groups = as_int(rtl_source_summary, "missing_source_groups")
    source_signature = rtl_source_summary.get("hardware_source_signature_sha256", "")
    add(
        rows,
        "rtl_source_binding",
        "Simulator evidence is bound to a concrete RTL/Chisel source signature.",
        PASS if source_files > 0 and missing_groups == 0 and source_signature else MISSING,
        f"{rtl_source_summary_path}: files={source_files}, missing_groups={missing_groups}",
        "" if source_files > 0 and missing_groups == 0 and source_signature else "RTL source manifest is missing files/groups/signature.",
        "Regenerate simulator outputs whenever the hardware source signature changes.",
    )

    blocked_path = results_root / "rtl_validation" / "rtl_blocked_cases.csv"
    add(
        rows,
        "base_mac_timing",
        "Blocked/X/zero-cycle RTL samples are explicitly separated from paper rows.",
        PASS if blocked > 0 and blocked_path.exists() else MISSING,
        f"{blocked_path}: direct_blocked_cases={blocked}",
        "" if blocked > 0 and blocked_path.exists() else "Blocked samples are not auditable.",
        "Keep blocked samples out of main performance tables.",
    )

    paper_gate_paths = [
        results_root / "person2_gemm" / "paper_tables" / "fig3_evidence_gate.csv",
        results_root / "synthetic_unet_trace" / "paper_tables" / "fig3_evidence_gate.csv",
        results_root / "softmax_smoke" / "paper_tables" / "fig3_evidence_gate.csv",
    ]
    existing_gate_paths = [p for p in paper_gate_paths if p.exists()]
    add(
        rows,
        "paper_gate",
        "Workload outputs carry confidence_grade and paper_use_policy gates.",
        PASS if len(existing_gate_paths) == len(paper_gate_paths) else PARTIAL,
        "; ".join(str(p) for p in existing_gate_paths),
        "" if len(existing_gate_paths) == len(paper_gate_paths) else "Some workload paper gates are missing.",
        "Do not give students ungated CSVs as paper-ready data.",
    )

    timeline_summary_path = results_root / "timeline_consistency" / "timeline_summary.csv"
    timeline_summary = first_row(timeline_summary_path)
    timeline_checked = as_int(timeline_summary, "checked_rows")
    timeline_failed = as_int(timeline_summary, "failed_rows")
    add(
        rows,
        "cycle_timeline",
        "Generated cycle and system interval timelines are internally consistent.",
        PASS if timeline_checked > 0 and timeline_failed == 0 else MISSING,
        f"{timeline_summary_path}: checked={timeline_checked}, failed={timeline_failed}",
        "" if timeline_checked > 0 and timeline_failed == 0 else "Timeline consistency report has failures or no checked rows.",
        "Fix interval accounting before trusting generated cycle totals.",
    )

    person2_value = first_row(results_root / "person2_gemm" / "value_check_summary.csv")
    synthetic_value = first_row(results_root / "synthetic_unet_trace" / "value_check_summary.csv")
    value_statuses = {
        "person2_gemm": person2_value.get("value_check_status", "missing"),
        "synthetic_unet_trace": synthetic_value.get("value_check_status", "missing"),
    }
    real_value_pass = all(v == "pass" for v in value_statuses.values())
    add(
        rows,
        "value_correctness",
        "Real workload simulator outputs are checked against RTL/golden values.",
        PASS if real_value_pass else MISSING,
        ", ".join(f"{k}={v}" for k, v in value_statuses.items()),
        "" if real_value_pass else "Current real workloads do not have pass-grade output-value evidence.",
        "Add golden outputs and RTL/testbench dumps for each paper workload.",
    )

    smoke_pass = first_row(results_root / "value_checker_smoke" / "pass_case" / "value_check_summary.csv")
    smoke_fail = first_row(results_root / "value_checker_smoke" / "fail_case" / "value_check_summary.csv")
    smoke_ok = smoke_pass.get("value_check_status") == "pass" and smoke_fail.get("value_check_status") == "fail"
    add(
        rows,
        "value_correctness",
        "Value checker itself catches pass and fail cases.",
        PASS if smoke_ok else MISSING,
        f"pass_case={smoke_pass.get('value_check_status','missing')}, fail_case={smoke_fail.get('value_check_status','missing')}",
        "" if smoke_ok else "The checker cannot yet be trusted as a gate.",
        "Keep this smoke test in every regression run.",
    )

    value_batch_path = results_root / "value_check_batch_smoke" / "value_readiness_summary.csv"
    value_batch_rows = read_rows(value_batch_path)
    value_batch_has_pass = any(row.get("main_value_ready_policy") == "ready_for_main_figure_value" for row in value_batch_rows)
    value_batch_has_fail_gate = any(
        row.get("value_check_status") == "fail" and row.get("main_value_ready_policy") == "not_ready_for_main_figure"
        for row in value_batch_rows
    )
    add(
        rows,
        "value_correctness",
        "Batch value-check gate accepts passing outputs and rejects failing outputs.",
        PASS if value_batch_has_pass and value_batch_has_fail_gate else MISSING,
        f"{value_batch_path}",
        "" if value_batch_has_pass and value_batch_has_fail_gate else "Batch value-check gate is not proven.",
        "Use this manifest path for real workload golden/RTL output comparisons.",
    )

    system = first_row(results_root / "system_calibration_smoke" / "system_calibration_summary.csv")
    measured = as_int(system, "measured_rows")
    mismatch = as_int(system, "mismatch_rows")
    system_status = PASS if measured > 0 and mismatch == 0 else PARTIAL if measured > 0 else MISSING
    add(
        rows,
        "system_timing",
        "Full-chip CPU/DMA/control timing is calibrated by measured RTL/testbench rows.",
        system_status,
        f"measured_rows={measured}, mismatch_rows={mismatch}",
        "" if system_status == PASS else "System timing is still smoke/projection, not main-table evidence.",
        "Collect real full-chip phase-cycle logs until mismatch_rows=0 for the claimed scope.",
    )

    batch_calib_path = results_root / "system_calibration_batch_smoke" / "calibration_readiness_summary.csv"
    batch_calib_rows = read_rows(batch_calib_path)
    batch_calib_ready = bool(batch_calib_rows) and all(
        row.get("paper_system_timing_policy") == "ready_for_main_figure_system_timing"
        for row in batch_calib_rows
    )
    add(
        rows,
        "system_timing",
        "Full-chip RTL log markers can be batch-parsed and gated as system timing evidence.",
        PASS if batch_calib_ready else MISSING,
        f"{batch_calib_path}",
        "" if batch_calib_ready else "System calibration batch gate is not passing.",
        "Use this path for real workload RTL/testbench logs before claiming system-level speedup.",
    )

    mechanism_summary_path = results_root / "mechanism_inventory" / "mechanism_summary.csv"
    mechanisms = read_rows(mechanism_summary_path)
    expected = {"mactree", "outlier", "INT8-INT4", "softmax", "zero-skip", "channel_group_sparsity"}
    found = {m.get("mechanism", "") for m in mechanisms}
    all_inventory = expected.issubset(found)
    all_inventory_only = mechanisms and all(m.get("integration_status") == "inventory_only_not_integrated" for m in mechanisms)
    add(
        rows,
        "mechanism_integration",
        "Six supplied optimization folders are inventoried and gated before use.",
        PASS if all_inventory else PARTIAL,
        f"{mechanism_summary_path}: found={','.join(sorted(found))}",
        "" if all_inventory else "Not all supplied mechanism folders are visible to the tool.",
        "Keep inventory as the first step before enabling any mechanism model.",
    )
    add(
        rows,
        "mechanism_integration",
        "Optimization mechanisms are not silently mixed into main timing without evidence.",
        PASS if all_inventory_only else BLOCKED,
        "integration_status=" + ("inventory_only_not_integrated" if all_inventory_only else "mixed_or_missing"),
        "" if all_inventory_only else "Mechanism integration status is ambiguous.",
        "Only enable a mechanism after it has timing, value, and quality gates.",
    )

    gate_files = [
        results_root / "mactree_profile" / "mactree_paper_gate.csv",
        results_root / "sparsity_profiles" / "sparsity_paper_gate.csv",
        results_root / "quant_outlier_profiles" / "quant_outlier_paper_gate.csv",
    ]
    add(
        rows,
        "mechanism_integration",
        "Mechanism-specific paper gates exist for MACTree, sparsity, quantization, and outlier paths.",
        PASS if all(p.exists() for p in gate_files) else PARTIAL,
        "; ".join(str(p) for p in gate_files if p.exists()),
        "" if all(p.exists() for p in gate_files) else "Some mechanism gates are missing.",
        "Use these gates to reject unvalidated mechanism speedup claims.",
    )

    softmax_gate = first_row(results_root / "softmax_smoke" / "paper_tables" / "fig3_evidence_gate.csv")
    softmax_grade = softmax_gate.get("confidence_grade", "missing")
    add(
        rows,
        "softmax",
        "Softmax has a standalone cycle projection but is not treated as integrated full-chip evidence.",
        PARTIAL if softmax_grade.startswith("C_") else MISSING,
        f"first confidence_grade={softmax_grade}",
        "Softmax lacks integrated RTL-clean timing/value validation.",
        "Use as appendix/projection until integrated softmax RTL evidence exists.",
    )

    batch_status_path = results_root / "batch_smoke" / "batch_run_status.csv"
    batch_ready_path = results_root / "batch_smoke" / "batch_readiness_summary.csv"
    batch_status = read_rows(batch_status_path)
    batch_ready = read_rows(batch_ready_path)
    batch_runs_ok = bool(batch_status) and all(r.get("run_status") == "pass" for r in batch_status)
    batch_gate_ok = bool(batch_ready) and all(r.get("batch_ready_policy") == "ready_for_gate_review" for r in batch_ready)
    add(
        rows,
        "delivery",
        "A student can run a manifest and obtain merged gated CSVs.",
        PASS if batch_runs_ok and batch_gate_ok else MISSING,
        f"{batch_status_path}; {batch_ready_path}",
        "" if batch_runs_ok and batch_gate_ok else "Batch runner or merged gates are not verified.",
        "Use the manifest template, then review main_figure_ready_policy before plotting.",
    )

    main_ready_rows = [r for r in batch_ready if r.get("main_figure_ready_policy") == "ready_for_main_figure"]
    add(
        rows,
        "delivery",
        "Batch outputs are directly ready for main paper figures.",
        PASS if main_ready_rows else PARTIAL,
        f"ready_for_main_figure_rows={len(main_ready_rows)}",
        "" if main_ready_rows else "Current smoke workloads remain projection/missing-value evidence.",
        "Add real workload value checks and full-chip calibration before declaring main-figure readiness.",
    )

    final_gate_path = results_root / "final_paper_gate_smoke" / "final_paper_data_summary.csv"
    final_gate = first_row(final_gate_path)
    final_rows = as_int(final_gate, "paper_rows")
    final_ready = as_int(final_gate, "ready_for_main_figure")
    final_not_ready = as_int(final_gate, "not_ready_for_main_figure")
    final_hardware_signature = final_gate.get("hardware_source_signature_sha256", "")
    final_gate_ok = final_rows > 0 and final_not_ready > 0 and final_ready == 0 and bool(final_hardware_signature)
    add(
        rows,
        "delivery",
        "Final paper-data gate merges workload, value, and system evidence before plotting.",
        PASS if final_gate_ok else MISSING,
        f"{final_gate_path}: ready={final_ready}, not_ready={final_not_ready}",
        "" if final_gate_ok else "Final paper-data gate is missing or not conservative.",
        "Use final_paper_data_policy as the single source of truth for main figures.",
    )

    evidence_manifest_path = results_root / "final_paper_gate_smoke" / "evidence_manifest.csv"
    evidence_rows = read_rows(evidence_manifest_path)
    required_roles = {
        "input_manifest",
        "input_workload_gate",
        "input_value_gate",
        "input_system_gate",
        "input_rtl_source_summary",
        "output_final_gate",
        "output_final_summary",
    }
    found_roles = {row.get("role", "") for row in evidence_rows}
    hashes_ok = evidence_rows and all(row.get("exists") == "True" and row.get("sha256") for row in evidence_rows)
    evidence_ok = required_roles.issubset(found_roles) and hashes_ok
    add(
        rows,
        "delivery",
        "Final paper-data gate has a traceable evidence manifest with file hashes.",
        PASS if evidence_ok else MISSING,
        f"{evidence_manifest_path}",
        "" if evidence_ok else "Evidence manifest is missing files or hashes.",
        "Keep this manifest with any plotted paper data for reproducibility review.",
    )

    export_summary_path = results_root / "main_figure_export_smoke" / "export_summary.csv"
    export_summary = first_row(export_summary_path)
    exported_rows = as_int(export_summary, "exported_main_figure_rows")
    rejected_rows = as_int(export_summary, "rejected_rows")
    source_hash_ok = bool(export_summary.get("source_final_gate_sha256", ""))
    export_hardware_signature = export_summary.get("hardware_source_signature_sha256", "")
    export_ok = source_hash_ok and bool(export_hardware_signature) and rejected_rows > 0 and exported_rows == 0
    add(
        rows,
        "delivery",
        "Main-figure export package contains only final-gate-approved rows.",
        PASS if export_ok else MISSING,
        f"{export_summary_path}: exported={exported_rows}, rejected={rejected_rows}",
        "" if export_ok else "Main-figure export package is missing or not conservative.",
        "Plotting scripts should consume this export package, not intermediate simulator CSVs.",
    )

    add(
        rows,
        "delivery",
        "The current tool can be claimed as a full cycle-accurate chip simulator.",
        BLOCKED,
        "Current validated scope is direct Base FLOOD MAC datapath plus projection hooks.",
        "DMA/control/SRAM/software scheduling/full-chip phase timing are not fully calibrated.",
        "Claim cycle-interval simulator now; upgrade to full cycle-accurate only after full-chip calibration passes.",
    )

    write_csv(out_dir / "readiness_requirements.csv", rows)
    counts = status_counts(rows)
    total = len(rows)
    strict_percent = round((counts.get(PASS, 0) / total) * 100, 2) if total else 0.0
    usable_percent = round(((counts.get(PASS, 0) + 0.5 * counts.get(PARTIAL, 0)) / total) * 100, 2) if total else 0.0
    summary = [
        {
            "total_requirements": str(total),
            "pass": str(counts.get(PASS, 0)),
            "partial": str(counts.get(PARTIAL, 0)),
            "missing": str(counts.get(MISSING, 0)),
            "blocked_by_evidence": str(counts.get(BLOCKED, 0)),
            "strict_pass_percent": f"{strict_percent:.2f}",
            "usable_with_caveats_percent": f"{usable_percent:.2f}",
            "goal_status": "not_complete_for_hpca_paper_data",
            "main_blocker": "real workload value checks and full-chip/system timing calibration",
        }
    ]
    write_csv(out_dir / "readiness_summary.csv", summary)

    readme = f"""# FLOOD Simulator Readiness Report

This report is intentionally conservative. It answers one question: can the
current tool be handed to students so that their output CSVs are directly usable
as paper data?

## Summary

- Strict pass: {counts.get(PASS, 0)}/{total} requirements ({strict_percent:.2f}%).
- Usable with caveats: {usable_percent:.2f}%.
- Goal status: not complete for HPCA paper data.
- Main blocker: real workload output-value checks and full-chip/system timing calibration.

## What Is Already Solid

- Base FLOOD MAC direct RTL-clean timing is currently all-pass.
- Blocked/X/zero-cycle RTL samples are explicitly separated.
- Paper-use gates exist, so projection rows are not silently mixed into main tables.
- Six optimization folders are inventoried and remain disabled unless evidence is added.

## What Still Blocks Paper-Ready Batch Runs

- Real workloads still lack pass-grade RTL/golden output-value evidence.
- Full-chip CPU/DMA/control timing is still a smoke/projection path.
- Softmax, MACTree, zero-skip, channel-group sparsity, INT8/INT4, and outlier paths
  are inventoried but not validated enough for main performance figures.

## Files

- `readiness_requirements.csv`: per-requirement evidence and blocker table.
- `readiness_summary.csv`: compact pass/partial/missing summary.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", default="results/flood_cycle_sim_v1")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/readiness_report")
    args = parser.parse_args()
    build_report(Path(args.results_root), Path(args.out_dir))


if __name__ == "__main__":
    main()
