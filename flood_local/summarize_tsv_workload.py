#!/usr/bin/env python3
import argparse
import csv
import math
import re
from pathlib import Path

FREQ_MHZ = 940.0


def avg(values):
    return sum(values) / len(values) if values else ""


def parse_log(path: Path):
    text = path.read_text(errors="ignore") if path.exists() else ""
    cycles = [int(x) for x in re.findall(r"Total execution cycles:\s*(\d+)", text)]
    wall = [float(x) for x in re.findall(r"Wall-clock time for simulation:\s*([0-9.]+)", text)]
    bw = [float(x) for x in re.findall(r"combined \|\s*([0-9.]+) GB/s aggregate", text)]
    systolic = [float(x) for x in re.findall(r"Systolic array \[\d+\] utilization\(%\):\s*([0-9.]+)", text)]
    vector = [float(x) for x in re.findall(r"Vector unit utilization\(%\):\s*([0-9.]+)", text)]
    dma = [int(x) for x in re.findall(r"DMA active_cycles:\s*(\d+)", text)]
    reads_writes = re.findall(r"combined \|.*\|\s*(\d+) reads,\s*(\d+) writes", text)
    reads = [int(r) for r, _ in reads_writes]
    writes = [int(w) for _, w in reads_writes]
    return {
        "num_simulations": len(cycles),
        "total_cycles": sum(cycles) if cycles else "",
        "max_cycles": max(cycles) if cycles else "",
        "latency_us": sum(cycles) / FREQ_MHZ if cycles else "",
        "wall_clock_s": sum(wall) if wall else "",
        "avg_dram_aggregate_gbps": avg(bw),
        "avg_systolic_util_pct": avg(systolic),
        "avg_vector_util_pct": avg(vector),
        "dma_active_cycles": sum(dma) if dma else "",
        "dram_reads": sum(reads) if reads else "",
        "dram_writes": sum(writes) if writes else "",
        "status": "ok" if "Simulation Done" in text else "check",
    }


def estimate_flood(row):
    base = float(row["total_cycles"] or 0)
    if not base:
        return None
    op = row["operator"]
    compute_speedup = {"conv": 1.15, "gemm": 1.20, "softmax": 1.30}.get(op, 1.10)
    metadata_ratio = {"conv": 0.03, "gemm": 0.02, "softmax": 0.01}.get(op, 0.03)
    outlier_ratio = {"conv": 0.02, "gemm": 0.025, "softmax": 0.005}.get(op, 0.02)
    switch_cycles = 10
    stall_reduction = 0.90
    flood_cycles = math.ceil(((base / compute_speedup) + base * metadata_ratio + base * outlier_ratio + switch_cycles) * stall_reduction)
    return {
        "id": row["id"],
        "workload": row["workload"],
        "stage": row["stage"],
        "operator": op,
        "shape_args": row["shape_args"],
        "baseline_cycles": int(base),
        "baseline_latency_us": base / FREQ_MHZ,
        "estimated_flood_cycles": flood_cycles,
        "estimated_flood_latency_us": flood_cycles / FREQ_MHZ,
        "estimated_speedup": base / flood_cycles,
        "compute_speedup_assumption": compute_speedup,
        "metadata_cycles": round(base * metadata_ratio, 2),
        "outlier_cycles": round(base * outlier_ratio, 2),
        "switch_cycles": switch_cycles,
        "note": "initial FLOOD post-processing estimate; replace assumptions before paper use",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload-tsv", required=True)
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--baseline-out", required=True)
    parser.add_argument("--flood-out", required=True)
    parser.add_argument("--readme-out", required=True)
    args = parser.parse_args()

    workload_tsv = Path(args.workload_tsv)
    log_dir = Path(args.log_dir)
    baseline_out = Path(args.baseline_out)
    flood_out = Path(args.flood_out)
    readme_out = Path(args.readme_out)
    baseline_out.parent.mkdir(parents=True, exist_ok=True)
    flood_out.parent.mkdir(parents=True, exist_ok=True)
    readme_out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with workload_tsv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            row["log_file"] = str(log_dir / f"{row['id']}.log")
            row.update(parse_log(Path(row["log_file"])))
            rows.append(row)

    with baseline_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    flood_rows = [x for x in (estimate_flood(row) for row in rows) if x]
    with flood_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flood_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flood_rows)

    with readme_out.open("w", encoding="utf-8") as f:
        f.write("# Synthetic UNet Unique Trace V1 Summary\n\n")
        f.write("Unique Conv/GEMM shapes traced from the synthetic UNet2DConditionModel forward pass.\n\n")
        for row in flood_rows:
            f.write(
                f"- {row['id']} {row['operator']} {row['shape_args']}: "
                f"baseline {row['baseline_cycles']} cycles, "
                f"FLOOD estimate {row['estimated_flood_cycles']} cycles, "
                f"speedup {row['estimated_speedup']:.3f}x.\n"
            )

    print("wrote", baseline_out)
    print("wrote", flood_out)
    print("wrote", readme_out)


if __name__ == "__main__":
    main()
