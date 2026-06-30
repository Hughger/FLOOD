#!/usr/bin/env python3
import csv
import math
import re
from pathlib import Path

OUT = Path("/root/autodl-tmp/torchsim_work/flood_results")
LOG_DIR = OUT / "logs"
LAYER_DIR = OUT / "layer_results"
SUMMARY_DIR = OUT / "summary"
FREQ_MHZ = 940.0

EXPERIMENTS = [
    ("gemm_128", "gemm", "128x128x128", LOG_DIR / "gemm_128.log"),
    ("conv_smoke", "conv", "N1_C32_H32_K320_R3_stride1_pad1", LOG_DIR / "conv_smoke.log"),
    ("softmax_512", "softmax", "512x512", LOG_DIR / "softmax_512.log"),
    ("diffusion_smoke", "diffusion_unet_smoke", "synthetic_unet_block", LOG_DIR / "diffusion_smoke_rerun.log"),
]


def average(values):
    return sum(values) / len(values) if values else ""


def parse_log(path):
    text = path.read_text(errors="ignore") if path.exists() else ""
    referenced_logs = re.findall(r'Simulation log is stored to "([^"]+\.log)"', text)
    child_text = ""
    for log_path in referenced_logs:
        child = Path(log_path)
        if child.exists():
            child_text += "\n" + child.read_text(errors="ignore")
    parse_text = text + child_text
    cycles = [int(x) for x in re.findall(r"Total execution cycles:\s*(\d+)", parse_text)]
    wall = [float(x) for x in re.findall(r"Wall-clock time for simulation:\s*([0-9.]+)", parse_text)]
    bw = [float(x) for x in re.findall(r"combined \|\s*([0-9.]+) GB/s aggregate", parse_text)]
    systolic = [float(x) for x in re.findall(r"Systolic array \[\d+\] utilization\(%\):\s*([0-9.]+)", parse_text)]
    vector = [float(x) for x in re.findall(r"Vector unit utilization\(%\):\s*([0-9.]+)", parse_text)]
    dma = [int(x) for x in re.findall(r"DMA active_cycles:\s*(\d+)", parse_text)]

    return {
        "num_simulations": len(cycles),
        "total_cycles": sum(cycles) if cycles else "",
        "max_cycles": max(cycles) if cycles else "",
        "latency_us": sum(cycles) / FREQ_MHZ if cycles else "",
        "wall_clock_s": sum(wall) if wall else "",
        "avg_dram_aggregate_gbps": average(bw),
        "avg_systolic_util_pct": average(systolic),
        "avg_vector_util_pct": average(vector),
        "dma_active_cycles": sum(dma) if dma else "",
        "status": "ok" if ("Simulation Done" in text or "Simulation Passed" in text) else "check",
    }


def main():
    LAYER_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for name, op, shape, path in EXPERIMENTS:
        row = {
            "experiment": name,
            "operator": op,
            "shape": shape,
            "log_file": str(path),
        }
        row.update(parse_log(path))
        rows.append(row)

    baseline_csv = LAYER_DIR / "baseline_cycles.csv"
    with baseline_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    speedup_by_op = {
        "gemm": 1.20,
        "conv": 1.15,
        "softmax": 1.30,
        "diffusion_unet_smoke": 1.18,
    }
    metadata_ratio = 0.03
    outlier_ratio = 0.02
    precision_switch_cycles = 2
    dataflow_switch_cycles = 8
    stall_reduction = 0.90
    memory_traffic_reduction = 0.85

    flood_rows = []
    for row in rows:
        base_cycles = float(row["total_cycles"] or 0)
        if not base_cycles:
            continue
        op = row["operator"]
        compute_speedup = speedup_by_op.get(op, 1.1)
        estimated_compute = base_cycles / compute_speedup
        metadata_cycles = base_cycles * metadata_ratio
        outlier_cycles = base_cycles * outlier_ratio
        switch_cycles = precision_switch_cycles + dataflow_switch_cycles
        flood_cycles = math.ceil(
            (estimated_compute + metadata_cycles + outlier_cycles + switch_cycles) * stall_reduction
        )
        flood_rows.append(
            {
                "experiment": row["experiment"],
                "operator": op,
                "shape": row["shape"],
                "baseline_cycles": int(base_cycles),
                "baseline_latency_us": base_cycles / FREQ_MHZ,
                "estimated_flood_cycles": flood_cycles,
                "estimated_flood_latency_us": flood_cycles / FREQ_MHZ,
                "estimated_speedup": base_cycles / flood_cycles if flood_cycles else "",
                "compute_speedup_assumption": compute_speedup,
                "memory_traffic_reduction_assumption": memory_traffic_reduction,
                "metadata_cycles": round(metadata_cycles, 2),
                "outlier_cycles": round(outlier_cycles, 2),
                "switch_cycles": switch_cycles,
                "note": "initial post-processing model; not final paper number",
            }
        )

    flood_csv = LAYER_DIR / "flood_layers.csv"
    summary_csv = SUMMARY_DIR / "flood_vs_baseline.csv"
    if flood_rows:
        fields = list(flood_rows[0].keys())
        for output in (flood_csv, summary_csv):
            with output.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(flood_rows)

    summary_md = SUMMARY_DIR / "README_small_loop.md"
    with summary_md.open("w") as f:
        f.write("# FLOOD PyTorchSim small-loop summary\n\n")
        f.write("This is the first pipeline check: PyTorchSim dense baseline plus FLOOD post-processing model.\n\n")
        for row in flood_rows:
            f.write(
                f"- {row['experiment']}: baseline {row['baseline_cycles']} cycles, "
                f"estimated FLOOD {row['estimated_flood_cycles']} cycles, "
                f"speedup {row['estimated_speedup']:.3f}x.\n"
            )

    print("wrote", baseline_csv)
    print("wrote", flood_csv)
    print("wrote", summary_csv)
    print("wrote", summary_md)


if __name__ == "__main__":
    main()
