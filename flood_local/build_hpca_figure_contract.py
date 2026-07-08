#!/usr/bin/env python3
"""Build a figure-by-figure HPCA paper-data contract.

The contract turns the manuscript test plan into a machine-checkable table. It
does not create new measurements; it records which figures already have enough
evidence for direct paper plotting and which still need real RTL/value/system
data.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


PASS = "pass"
PARTIAL = "partial"
MISSING = "missing"
BLOCKED = "blocked"


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def first_row(path: Path) -> dict[str, str]:
    rows = read_rows(path)
    return rows[0] if rows else {}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["status"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def as_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "0") or 0))
    except ValueError:
        return 0


def has_rows(path: Path) -> bool:
    return bool(read_rows(path))


def all_value_ready(path: Path) -> bool:
    rows = read_rows(path)
    return bool(rows) and all(row.get("main_value_ready_policy") == "ready_for_main_figure_value" for row in rows)


def all_system_ready(path: Path) -> bool:
    rows = read_rows(path)
    return bool(rows) and all(row.get("paper_system_timing_policy") == "ready_for_main_figure_system_timing" for row in rows)


def add(
    rows: list[dict[str, Any]],
    figure_id: str,
    figure_goal: str,
    required_outputs: str,
    status: str,
    current_evidence: str,
    blockers: str,
    next_action: str,
    paper_use_policy: str,
) -> None:
    rows.append(
        {
            "figure_id": figure_id,
            "figure_goal": figure_goal,
            "required_outputs": required_outputs,
            "status": status,
            "current_evidence": current_evidence,
            "blockers": blockers,
            "next_action": next_action,
            "paper_use_policy": paper_use_policy,
        }
    )


def build_contract(results_root: Path, legacy_micro_dir: Path, out_dir: Path, backend_root: Path | None = None) -> None:
    rows: list[dict[str, Any]] = []

    backend_root = backend_root or Path("results/flood_pytorchsim_backend_v1")
    operator_comp = backend_root / "workload_composition_v1" / "operator_composition.csv"
    bottleneck = backend_root / "workload_composition_v1" / "workload_bottleneck_table.csv"
    final_summary = first_row(results_root / "final_paper_gate_smoke" / "final_paper_data_summary.csv")
    ready_rows = as_int(final_summary, "ready_for_main_figure")
    rejected_rows = as_int(final_summary, "not_ready_for_main_figure")
    rtl_summary = first_row(results_root / "rtl_validation" / "rtl_validation_summary.csv")
    rtl_clean_pass = (
        as_int(rtl_summary, "rtl_clean_cases") > 0
        and as_int(rtl_summary, "passed_cases") == as_int(rtl_summary, "rtl_clean_cases")
        and as_int(rtl_summary, "failed_cases") == 0
    )
    value_ready = all_value_ready(results_root / "value_check_batch_smoke" / "value_readiness_summary.csv")
    system_ready = all_system_ready(results_root / "system_calibration_batch_smoke" / "calibration_readiness_summary.csv")
    timeline_ok = first_row(results_root / "timeline_consistency" / "timeline_summary.csv").get("failed_rows") == "0"
    mechanism_rows = read_rows(results_root / "mechanism_inventory" / "mechanism_summary.csv")
    mechanisms_inventory_only = bool(mechanism_rows) and all(
        row.get("integration_status") == "inventory_only_not_integrated" for row in mechanism_rows
    )
    legacy_ppa = legacy_micro_dir / "legacy_ppa.csv"

    fig1_ok = has_rows(operator_comp) and has_rows(bottleneck)
    add(
        rows,
        "Fig.1",
        "Problem motivation: workload/operator composition and baseline bottlenecks.",
        "operator composition, latency bottleneck table, baseline utilization evidence",
        PASS if fig1_ok else MISSING,
        f"operator_composition={operator_comp.exists()}, bottleneck_table={bottleneck.exists()}",
        "" if fig1_ok else "Missing workload composition or baseline bottleneck table.",
        "Regenerate workload composition from PyTorchSim traces and keep source labels.",
        "Can support motivation only; not a performance claim by itself.",
    )

    fig2_status = PARTIAL if has_rows(results_root / "rtl_source_manifest" / "rtl_source_summary.csv") else MISSING
    add(
        rows,
        "Fig.2",
        "Architecture overview and module/resource mapping.",
        "RTL module map, area/power/resource breakdown, data-path mapping",
        fig2_status,
        f"rtl_source_summary={has_rows(results_root / 'rtl_source_manifest' / 'rtl_source_summary.csv')}, legacy_ppa={legacy_ppa.exists()}",
        "Current area/power is legacy/reference unless current synthesis reports are ingested.",
        "Ingest current 28nm synthesis area/power reports and map each major module.",
        "Architecture diagram is usable; PPA bars need current-source evidence.",
    )

    fig3_status = PASS if rtl_clean_pass and value_ready else PARTIAL if rtl_clean_pass else MISSING
    add(
        rows,
        "Fig.3",
        "PyTorchSim/golden/RTL validation data chain.",
        "golden source, RTL source, max error, pass rate, cycle source, provenance",
        fig3_status,
        f"rtl_clean_pass={rtl_clean_pass}, value_ready={value_ready}",
        "" if fig3_status == PASS else "Real workload output-value evidence is still missing or not all pass.",
        "Add golden and RTL output dumps for the paper workloads, then rerun value batch gates.",
        "Use partial validation for method section; main claims need value_ready=true.",
    )

    fig4_status = PARTIAL if timeline_ok else MISSING
    add(
        rows,
        "Fig.4",
        "FSM and multi-core/tile cycle breakdown.",
        "load/compute/transfer/writeback/switch/stall cycles and timeline consistency",
        fig4_status,
        f"timeline_consistency_failed_rows={first_row(results_root / 'timeline_consistency' / 'timeline_summary.csv').get('failed_rows','missing')}",
        "Stall/overlap counters are not fully calibrated from full-chip RTL.",
        "Export or parse full-chip phase markers for config/DMA/MAC/writeback/stall.",
        "Can show cycle decomposition draft; not final overlap/stall claim yet.",
    )

    add(
        rows,
        "Fig.5",
        "Quality preservation: PSNR/SSIM/LPIPS/FID/CLIPScore or numerical error.",
        "FP/reference output, optimized output, quality metrics, output samples",
        MISSING,
        "No pass-grade model-level quality table is connected to the current final gate.",
        "Quality runner outputs are not ingested as paper-ready evidence.",
        "Run quality metrics for FP/reference, INT8, INT4, mixed, mixed+outlier, and softmax variants.",
        "Do not plot as final paper quality data yet.",
    )

    fig6_status = PASS if ready_rows > 0 and value_ready and system_ready else MISSING
    add(
        rows,
        "Fig.6",
        "Main performance: latency, throughput, energy/power, utilization.",
        "baseline cycles, FLOOD cycles, speedup, energy/power, utilization, traffic",
        fig6_status,
        f"final_ready_rows={ready_rows}, rejected_rows={rejected_rows}, value_ready={value_ready}, system_ready={system_ready}",
        "" if fig6_status == PASS else "No final-gate-approved rows with both value and full-chip timing evidence.",
        "Run P0 RTL tasks until value and system gates are ready, then export main figure rows.",
        "Blocked from direct paper plotting until final_ready_rows>0.",
    )

    fig7_status = MISSING if mechanisms_inventory_only else PARTIAL
    add(
        rows,
        "Fig.7",
        "Ablation: incremental and leave-one-out contribution of each mechanism.",
        "Base, +sparsity, +mixed precision, +outlier, +softmax, +adaptive dataflow, leave-one-out rows",
        fig7_status,
        f"mechanism_rows={len(mechanism_rows)}, inventory_only={mechanisms_inventory_only}",
        "Mechanism folders are inventoried but not integrated/validated enough for final ablation.",
        "For each mechanism, add timing, value correctness, quality, and source gate evidence.",
        "Use current rows only as planning/proxy tables.",
    )

    fig8_status = PARTIAL if legacy_ppa.exists() else MISSING
    add(
        rows,
        "Fig.8",
        "Area, power, TOPS/W, GOPS/mm2, scaling/bandwidth/buffer sensitivity.",
        "current synthesis area/power, frequency, throughput normalization, scaling sweep",
        fig8_status,
        f"legacy_ppa={legacy_ppa.exists()}, process=28nm, freq_mhz=330",
        "Current PPA source is not yet bound to this exact RTL source signature.",
        "Ingest current synthesis PPA and add scaling/bandwidth/buffer sweep outputs.",
        "Legacy PPA can be cited as reference, not as new final measured data.",
    )

    write_csv(out_dir / "hpca_figure_contract.csv", rows)
    counts = {PASS: 0, PARTIAL: 0, MISSING: 0, BLOCKED: 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    p0_figs = {"Fig.1", "Fig.2", "Fig.3", "Fig.4", "Fig.6", "Fig.7"}
    p0_ready = sum(1 for row in rows if row["figure_id"] in p0_figs and row["status"] == PASS)
    summary = [
        {
            "figures": str(len(rows)),
            "paper_ready_figures": str(counts[PASS]),
            "partial_figures": str(counts[PARTIAL]),
            "missing_figures": str(counts[MISSING]),
            "blocked_figures": str(counts[BLOCKED]),
            "p0_ready_figures": str(p0_ready),
            "p0_total_figures": str(len(p0_figs)),
            "final_gate_ready_rows": str(ready_rows),
            "goal_status": "ready_for_direct_paper_plotting" if ready_rows > 0 and counts[MISSING] == 0 else "not_ready_for_direct_paper_plotting",
            "main_blocker": "real RTL value outputs, full-chip timing calibration, mechanism/quality/PPA evidence",
        }
    ]
    write_csv(out_dir / "hpca_figure_contract_summary.csv", summary)
    readme = """# HPCA Figure Contract

This directory maps the manuscript Fig.1-Fig.8 plan to concrete evidence files.

Rules:

- `pass` means the current evidence can support that figure's data claim.
- `partial` means useful draft/supporting evidence exists, but not enough for a
  final main-paper numerical claim.
- `missing` means the required runner/data source is not connected yet.
- Plotting should use final-gate-approved rows only; this contract explains why
  a figure is or is not ready.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", default="results/flood_cycle_sim_v1")
    parser.add_argument("--legacy-micro-dir", default="results/flood_pytorchsim_backend_v1/legacy_micro_data_v1")
    parser.add_argument("--backend-root", default="results/flood_pytorchsim_backend_v1")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/hpca_figure_contract")
    args = parser.parse_args()
    build_contract(Path(args.results_root), Path(args.legacy_micro_dir), Path(args.out_dir), Path(args.backend_root))


if __name__ == "__main__":
    main()
