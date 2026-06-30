#!/usr/bin/env python3
"""Paper-level FLOOD comparison scenarios.

The current FLOOD RTL has 16 x 32x32 tiles with tLatency=4, while the
PyTorchSim baseline used in this project is a TPUv3-like 2 x 128x128 systolic
configuration. Directly comparing those two is not a fair paper comparison.

This script keeps the current RTL estimate, then adds normalized scenarios:

1. current_rtl
2. equal_peak_dense
3. flood_conservative
4. flood_main
5. flood_aggressive

The last three scenarios are explicit assumptions for a paper-level target
architecture. They must be backed by RTL/FPGA/ASIC or cited sensitivity analysis
before being used as final claims.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flood_rtl_aware_model import FREQ_MHZ, RTL, estimate_operator  # noqa: E402


PYTORCHSIM_PEAK_MACS_PER_CYCLE = 2 * 128 * 128
FLOOD_CURRENT_MACS_PER_CYCLE = RTL["tile_size"] * RTL["row_size"] * RTL["col_size"] / RTL["t_latency"]
PEAK_SCALE = PYTORCHSIM_PEAK_MACS_PER_CYCLE / FLOOD_CURRENT_MACS_PER_CYCLE


SCENARIOS = {
    "equal_peak_dense": {
        "compute_factor": 1.00,
        "memory_factor": 1.00,
        "metadata_ratio": 0.00,
        "outlier_ratio": 0.00,
        "switch_cycles": 0,
        "softmax_speedup": 1.00,
        "note": "equal peak MAC/cycle normalization only",
    },
    "flood_conservative": {
        "compute_factor": 0.90,
        "memory_factor": 0.85,
        "metadata_ratio": 0.03,
        "outlier_ratio": 0.02,
        "switch_cycles": 10,
        "softmax_speedup": 1.20,
        "note": "equal peak + conservative FLOOD dataflow/sparsity assumptions",
    },
    "flood_main": {
        "compute_factor": 0.75,
        "memory_factor": 0.75,
        "metadata_ratio": 0.04,
        "outlier_ratio": 0.02,
        "switch_cycles": 10,
        "softmax_speedup": 1.35,
        "note": "equal peak + main FLOOD paper-level assumptions",
    },
    "flood_aggressive": {
        "compute_factor": 0.60,
        "memory_factor": 0.65,
        "metadata_ratio": 0.05,
        "outlier_ratio": 0.03,
        "switch_cycles": 12,
        "softmax_speedup": 1.55,
        "note": "equal peak + aggressive sensitivity assumptions",
    },
}


def fnum(row: dict[str, str], key: str) -> float:
    try:
        value = row.get(key, "")
        return float(value) if value not in ("", None) else 0.0
    except ValueError:
        return 0.0


def scenario_cycles_from_breakdown(est: dict[str, float | int | str], scenario: dict[str, float | int | str]) -> dict[str, float]:
    scale = PEAK_SCALE
    compute = float(est["rtl_compute_cycles"]) / scale
    weight = float(est["rtl_weight_load_cycles"]) / scale
    activation = float(est["rtl_activation_load_cycles"]) / scale
    output = float(est["rtl_output_store_cycles"]) / scale
    shift = float(est["rtl_shift_add_cycles"]) / scale
    noc = float(est["rtl_noc_reduce_cycles"]) / scale
    tile_output = float(est.get("rtl_tile_output_transfer_cycles", 0)) / scale
    arbiter = float(est.get("rtl_output_arbiter_cycles", 0)) / scale
    joint = float(est.get("rtl_joint_sram_cycles", 0)) / scale

    compute *= float(scenario["compute_factor"])
    weight *= float(scenario["memory_factor"])
    activation *= float(scenario["memory_factor"])
    output *= float(scenario["memory_factor"])
    tile_output *= float(scenario["memory_factor"])
    arbiter *= float(scenario["memory_factor"])
    joint *= float(scenario["memory_factor"])

    main = max(compute, weight, activation)
    metadata = main * float(scenario["metadata_ratio"])
    outlier = main * float(scenario["outlier_ratio"])
    total = main + output + shift + noc + tile_output + arbiter + joint + metadata + outlier + float(scenario["switch_cycles"])
    return {
        "compute_cycles": compute,
        "weight_load_cycles": weight,
        "activation_load_cycles": activation,
        "output_store_cycles": output,
        "metadata_cycles": metadata,
        "outlier_cycles": outlier,
        "shift_add_cycles": shift,
        "noc_reduce_cycles": noc,
        "tile_output_transfer_cycles": tile_output,
        "output_arbiter_cycles": arbiter,
        "joint_sram_cycles": joint,
        "total_cycles": total,
    }


def scenario_for_row(row: dict[str, str], scenario_name: str, scenario: dict[str, float | int | str]) -> dict[str, str | float]:
    baseline = fnum(row, "total_cycles")
    op = row.get("operator", "")
    shape = row.get("shape_args", "")

    out: dict[str, str | float] = {
        "dataset": row.get("dataset", ""),
        "id": row.get("id", ""),
        "workload": row.get("workload", ""),
        "stage": row.get("stage", ""),
        "operator": op,
        "shape_args": shape,
        "scenario": scenario_name,
        "pytorchsim_cycles": baseline,
        "pytorchsim_latency_us": baseline / FREQ_MHZ if baseline else "",
        "peak_scale_vs_current_rtl": PEAK_SCALE,
        "note": str(scenario["note"]),
    }

    if op in {"conv", "gemm"}:
        est = estimate_operator(op, shape)
        if scenario_name == "current_rtl":
            total = float(est["rtl_total_cycles"])
            breakdown = {
                "compute_cycles": float(est["rtl_compute_cycles"]),
                "weight_load_cycles": float(est["rtl_weight_load_cycles"]),
                "activation_load_cycles": float(est["rtl_activation_load_cycles"]),
                "output_store_cycles": float(est["rtl_output_store_cycles"]),
                "metadata_cycles": 0.0,
                "outlier_cycles": 0.0,
                "shift_add_cycles": float(est["rtl_shift_add_cycles"]),
                "noc_reduce_cycles": float(est["rtl_noc_reduce_cycles"]),
                "tile_output_transfer_cycles": float(est.get("rtl_tile_output_transfer_cycles", 0)),
                "output_arbiter_cycles": float(est.get("rtl_output_arbiter_cycles", 0)),
                "joint_sram_cycles": float(est.get("rtl_joint_sram_cycles", 0)),
                "total_cycles": total,
            }
        else:
            breakdown = scenario_cycles_from_breakdown(est, scenario)
            total = breakdown["total_cycles"]
        out.update({k: round(v, 4) for k, v in breakdown.items()})
        out["flood_cycles"] = round(total, 4)
        out["flood_latency_us"] = round(total / FREQ_MHZ, 6)
        out["speedup_vs_pytorchsim"] = round(baseline / total, 6) if total and baseline else ""
        out["compute_utilization"] = est["rtl_compute_utilization"]
        return out

    if op == "softmax":
        if scenario_name == "current_rtl":
            out["note"] = "softmax is not implemented in the current visible FLOOD RTL model"
            out["flood_cycles"] = ""
            out["speedup_vs_pytorchsim"] = ""
            return out
        speedup = float(scenario["softmax_speedup"])
        total = baseline / speedup if speedup else baseline
        out.update(
            {
                "compute_cycles": round(total, 4),
                "weight_load_cycles": 0.0,
                "activation_load_cycles": "",
                "output_store_cycles": "",
                "metadata_cycles": "",
                "outlier_cycles": "",
                "shift_add_cycles": "",
                "noc_reduce_cycles": "",
                "tile_output_transfer_cycles": "",
                "output_arbiter_cycles": "",
                "joint_sram_cycles": "",
                "total_cycles": round(total, 4),
                "flood_cycles": round(total, 4),
                "flood_latency_us": round(total / FREQ_MHZ, 6),
                "speedup_vs_pytorchsim": round(speedup, 6),
                "compute_utilization": "",
                "note": str(scenario["note"]) + "; softmax modeled as planned vector/softmax unit sensitivity",
            }
        )
        return out

    out["note"] = "unsupported operator"
    return out


def summarize(rows: list[dict[str, str | float]]) -> list[dict[str, str | float]]:
    groups: dict[tuple[str, str, str], list[dict[str, str | float]]] = {}
    for row in rows:
        if row.get("flood_cycles", "") == "":
            continue
        key = (str(row.get("dataset", "")), str(row.get("scenario", "")), str(row.get("operator", "")))
        groups.setdefault(key, []).append(row)

    out = []
    for (dataset, scenario, operator), items in sorted(groups.items()):
        base = sum(float(r.get("pytorchsim_cycles") or 0) for r in items)
        flood = sum(float(r.get("flood_cycles") or 0) for r in items)
        out.append(
            {
                "dataset": dataset,
                "scenario": scenario,
                "operator": operator,
                "num_rows": len(items),
                "pytorchsim_cycles": round(base, 4),
                "flood_cycles": round(flood, 4),
                "flood_latency_us": round(flood / FREQ_MHZ, 6),
                "speedup_vs_pytorchsim": round(base / flood, 6) if flood else "",
            }
        )
    return out


def write_csv(path: Path, rows: list[dict[str, str | float]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_readme(path: Path, summary_rows: list[dict[str, str | float]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("# FLOOD Paper-Level Comparison\n\n")
        f.write("This comparison separates current RTL scale from paper-level normalized scenarios.\n\n")
        f.write(f"- PyTorchSim baseline peak assumption: {PYTORCHSIM_PEAK_MACS_PER_CYCLE:.0f} MAC/cycle\n")
        f.write(f"- Current FLOOD RTL peak estimate: {FLOOD_CURRENT_MACS_PER_CYCLE:.0f} MAC/cycle\n")
        f.write(f"- Equal-peak scale factor: {PEAK_SCALE:.2f}x\n\n")
        f.write("| Dataset | Scenario | Operator | Rows | PyTorchSim cycles | FLOOD cycles | Speedup |\n")
        f.write("|---|---|---|---:|---:|---:|---:|\n")
        for row in summary_rows:
            f.write(
                f"| {row['dataset']} | {row['scenario']} | {row['operator']} | {row['num_rows']} | "
                f"{row['pytorchsim_cycles']} | {row['flood_cycles']} | {row['speedup_vs_pytorchsim']}x |\n"
            )
        f.write("\n## Notes\n\n")
        f.write("- `current_rtl` is tied to the visible 16-tile FLOOD implementation.\n")
        f.write("- `equal_peak_dense` normalizes current FLOOD compute resources to PyTorchSim baseline peak MAC/cycle.\n")
        f.write("- `flood_conservative`, `flood_main`, and `flood_aggressive` are paper-level sensitivity scenarios.\n")
        f.write("- Softmax is only included in paper-level scenarios as a planned vector/softmax-unit sensitivity, not current RTL.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--inputs", nargs="+", required=True, help="dataset=csv")
    args = parser.parse_args()

    inputs = []
    for item in args.inputs:
        dataset, path = item.split("=", 1)
        with Path(path).open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["dataset"] = dataset
                inputs.append(row)

    scenario_defs = {"current_rtl": {"note": "current visible FLOOD RTL scale", "softmax_speedup": 1.0}, **SCENARIOS}
    rows = []
    for row in inputs:
        for name, scenario in scenario_defs.items():
            rows.append(scenario_for_row(row, name, scenario))

    out_dir = Path(args.out_dir)
    details = out_dir / "paper_comparison_details.csv"
    summary = out_dir / "paper_comparison_summary.csv"
    readme = out_dir / "paper_comparison_readable.md"
    summary_rows = summarize(rows)
    write_csv(details, rows)
    write_csv(summary, summary_rows)
    write_readme(readme, summary_rows)
    print("wrote", details)
    print("wrote", summary)
    print("wrote", readme)


if __name__ == "__main__":
    main()
