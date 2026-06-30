#!/usr/bin/env python3
"""FLOOD backend pipeline for PyTorchSim-generated workloads.

This script treats PyTorchSim as the workload/baseline provider and emits a
FLOOD backend result package:

1. current RTL-aware FLOOD estimates
2. equal-peak and paper-level sensitivity scenarios
3. operator/workmode summaries
4. an RTL calibration case list

The FLOOD numbers are not RTL simulation results. They are analytical backend
estimates that should be calibrated with small RTL simulations.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flood_paper_compare import PEAK_SCALE, SCENARIOS, scenario_for_row  # noqa: E402
from flood_rtl_aware_model import FREQ_MHZ, enrich_row  # noqa: E402


def fnum(value: Any) -> float:
    if value in ("", None):
        return 0.0
    return float(value)


def read_inputs(items: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in items:
        dataset, path = item.split("=", 1)
        with Path(path).open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["dataset"] = dataset
                rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def current_rtl_rows(inputs: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in inputs:
        out = enrich_row(row)
        baseline = fnum(row.get("total_cycles") or row.get("baseline_cycles"))
        out["pytorchsim_cycles"] = baseline
        out["pytorchsim_latency_us"] = baseline / FREQ_MHZ if baseline else ""
        out["backend_scenario"] = "current_rtl"
        rows.append(out)
    return rows


def scenario_rows(inputs: list[dict[str, str]]) -> list[dict[str, Any]]:
    scenario_defs = {"current_rtl": {"note": "current visible FLOOD RTL scale", "softmax_speedup": 1.0}, **SCENARIOS}
    rows: list[dict[str, Any]] = []
    for row in inputs:
        for name, scenario in scenario_defs.items():
            rows.append(scenario_for_row(row, name, scenario))
    return rows


def summarize_current(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        op = str(row.get("operator", ""))
        if op not in {"conv", "gemm"}:
            continue
        key = (str(row.get("dataset", "")), op, str(row.get("rtl_workmode_class", "")))
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (dataset, op, workmode), items in sorted(groups.items()):
        base = sum(fnum(r.get("pytorchsim_cycles")) for r in items)
        rtl = sum(fnum(r.get("rtl_total_cycles")) for r in items)
        compute = sum(fnum(r.get("rtl_compute_cycles")) for r in items)
        memory = sum(
            max(
                fnum(r.get("rtl_weight_load_cycles")),
                fnum(r.get("rtl_activation_load_cycles")),
            )
            for r in items
        )
        output = sum(fnum(r.get("rtl_output_store_cycles")) for r in items)
        arbiter = sum(fnum(r.get("rtl_output_arbiter_cycles")) for r in items)
        shift = sum(fnum(r.get("rtl_shift_add_cycles")) for r in items)
        joint = sum(fnum(r.get("rtl_joint_sram_cycles")) for r in items)
        out.append(
            {
                "dataset": dataset,
                "operator": op,
                "rtl_workmode_class": workmode,
                "num_rows": len(items),
                "pytorchsim_cycles": round(base, 4),
                "flood_current_rtl_cycles": round(rtl, 4),
                "speedup_vs_pytorchsim": round(base / rtl, 6) if rtl else "",
                "compute_cycles": round(compute, 4),
                "max_load_cycles_sum": round(memory, 4),
                "output_store_cycles": round(output, 4),
                "output_arbiter_cycles": round(arbiter, 4),
                "shift_add_cycles": round(shift, 4),
                "joint_sram_cycles": round(joint, 4),
            }
        )
    return out


def summarize_scenarios(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("flood_cycles", "") == "":
            continue
        key = (str(row.get("dataset", "")), str(row.get("scenario", "")))
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (dataset, scenario), items in sorted(groups.items()):
        base = sum(fnum(r.get("pytorchsim_cycles")) for r in items)
        flood = sum(fnum(r.get("flood_cycles")) for r in items)
        ops = ",".join(sorted({str(r.get("operator", "")) for r in items}))
        out.append(
            {
                "dataset": dataset,
                "scenario": scenario,
                "operators": ops,
                "pytorchsim_cycles": round(base, 4),
                "flood_cycles": round(flood, 4),
                "flood_latency_us": round(flood / FREQ_MHZ, 6),
                "speedup_vs_pytorchsim": round(base / flood, 6) if flood else "",
            }
        )
    return out


def calibration_cases(current_rows: list[dict[str, Any]], max_cases: int) -> list[dict[str, Any]]:
    candidates = [r for r in current_rows if r.get("operator") in {"conv", "gemm"}]
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    priority = [
        ("gemm", "gemm"),
        ("conv", "pointwise_conv"),
        ("conv", "spatial_conv"),
    ]
    for op, workmode in priority:
        matches = [r for r in candidates if r.get("operator") == op and r.get("rtl_workmode_class") == workmode]
        matches.sort(key=lambda r: fnum(r.get("rtl_total_cycles")))
        for idx in [0, len(matches) // 2, len(matches) - 1]:
            if not matches:
                continue
            row = matches[idx]
            key = (str(row.get("dataset")), str(row.get("id") or row.get("workload") or row.get("shape_args")))
            if key not in seen:
                selected.append(row)
                seen.add(key)
            if len(selected) >= max_cases:
                break
        if len(selected) >= max_cases:
            break

    if len(selected) < max_cases:
        for row in sorted(candidates, key=lambda r: fnum(r.get("rtl_total_cycles")), reverse=True):
            key = (str(row.get("dataset")), str(row.get("id") or row.get("workload") or row.get("shape_args")))
            if key in seen:
                continue
            selected.append(row)
            seen.add(key)
            if len(selected) >= max_cases:
                break

    out: list[dict[str, Any]] = []
    for i, row in enumerate(selected, start=1):
        workmode = str(row.get("rtl_workmode_class", ""))
        signals = [
            "start/done",
            "weight_sram*_bram_r_en",
            "input feature write/read path",
            "output_sram*_bram_w_en",
            "Tile.outputNoc.valid/ready",
            "Cluster.outputArbiter.io.out.valid/ready",
        ]
        if workmode == "spatial_conv":
            signals.extend(["Tile.shiftState", "Tile.nocState", "joint_sram*_r_en/w_en"])
        out.append(
            {
                "case_id": f"calib_{i:02d}",
                "dataset": row.get("dataset", ""),
                "source_id": row.get("id") or row.get("workload") or "",
                "operator": row.get("operator", ""),
                "shape_args": row.get("shape_args", ""),
                "rtl_workmode_class": workmode,
                "model_predicted_cycles": row.get("rtl_total_cycles", ""),
                "pytorchsim_cycles": row.get("pytorchsim_cycles", ""),
                "rtl_sim_cycles": "",
                "error_percent": "",
                "validation_goal": validation_goal(workmode),
                "signals_to_probe": "; ".join(signals),
            }
        )
    return out


def validation_goal(workmode: str) -> str:
    if workmode == "pointwise_conv":
        return "verify k=1 pointwise fast path, no shift-add, single output transfer"
    if workmode == "spatial_conv":
        return "verify k>1 shift-add, second output transfer, joint/output path"
    if workmode == "gemm":
        return "verify dense CIM compute, weight/input movement, output arbitration"
    return "verify unsupported or non-CIM path"


def write_readme(path: Path, current_summary: list[dict[str, Any]], scenario_summary: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD PyTorchSim Backend Package v1\n\n")
        fh.write("This package uses PyTorchSim outputs as workload/baseline data and applies a FLOOD RTL-aware backend model.\n\n")
        fh.write("## Important Interpretation\n\n")
        fh.write("- PyTorchSim cycles are baseline NPU results.\n")
        fh.write("- `current_rtl` FLOOD cycles are analytical estimates from visible FLOOD RTL/Chisel structure.\n")
        fh.write("- Equal-peak and FLOOD scenarios are normalized/sensitivity results, not RTL simulation.\n")
        fh.write("- Use `calibration_cases.csv` to run small RTL simulations and fill `rtl_sim_cycles`.\n\n")
        fh.write("## Current RTL Summary\n\n")
        fh.write("| Dataset | Operator | Workmode | Rows | PyTorchSim cycles | FLOOD cycles | Speedup |\n")
        fh.write("|---|---|---|---:|---:|---:|---:|\n")
        for row in current_summary:
            fh.write(
                f"| {row['dataset']} | {row['operator']} | {row['rtl_workmode_class']} | {row['num_rows']} | "
                f"{row['pytorchsim_cycles']} | {row['flood_current_rtl_cycles']} | {row['speedup_vs_pytorchsim']}x |\n"
            )
        fh.write("\n## Scenario Summary\n\n")
        fh.write("| Dataset | Scenario | Operators | PyTorchSim cycles | FLOOD cycles | Speedup |\n")
        fh.write("|---|---|---|---:|---:|---:|\n")
        for row in scenario_summary:
            fh.write(
                f"| {row['dataset']} | {row['scenario']} | {row['operators']} | "
                f"{row['pytorchsim_cycles']} | {row['flood_cycles']} | {row['speedup_vs_pytorchsim']}x |\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--inputs", nargs="+", required=True, help="dataset=baseline.csv")
    parser.add_argument("--max-calibration-cases", type=int, default=10)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = read_inputs(args.inputs)
    current = current_rtl_rows(inputs)
    scenarios = scenario_rows(inputs)
    current_summary = summarize_current(current)
    scenario_summary = summarize_scenarios(scenarios)
    calib = calibration_cases(current, args.max_calibration_cases)

    write_csv(out_dir / "flood_current_rtl_backend_details.csv", current)
    write_csv(out_dir / "flood_current_rtl_backend_summary.csv", current_summary)
    write_csv(out_dir / "flood_backend_scenario_details.csv", scenarios)
    write_csv(out_dir / "flood_backend_scenario_summary.csv", scenario_summary)
    write_csv(out_dir / "calibration_cases.csv", calib)
    (out_dir / "calibration_template.json").write_text(
        json.dumps(
            {
                "purpose": "Fill rtl_sim_cycles after FLOOD RTL simulation, then use it to calibrate the backend.",
                "frequency_mhz": FREQ_MHZ,
                "peak_scale_vs_current_rtl": PEAK_SCALE,
                "recommended_error_targets": {
                    "microbench_average_error_percent": "<= 20 for preliminary paper use",
                    "microbench_max_error_percent": "<= 35 unless explained by unsupported control behavior",
                },
                "calibration_knobs": [
                    "compute_memory_overlap",
                    "output_arbiter_cycles",
                    "joint_sram_cycles",
                    "tile_output_transfer_cycles",
                    "pipeline_stall_cycles",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_readme(out_dir / "README.md", current_summary, scenario_summary)

    print(f"wrote FLOOD backend package to {out_dir}")


if __name__ == "__main__":
    main()
