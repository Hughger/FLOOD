#!/usr/bin/env python3
import csv
import math
import re
from pathlib import Path

OUT = Path("/root/autodl-tmp/torchsim_work/flood_results")
LOG_DIR = OUT / "logs" / "batch_ops"
LAYER_DIR = OUT / "layer_results"
SUMMARY_DIR = OUT / "summary"
FREQ_MHZ = 940.0

WORKLOADS = [
    ("unet_conv_64_320_320", "SD_UNet", "early_down", "conv", "1 64 64 320 320 3 1 1", "UNet early feature conv proxy"),
    ("unet_conv_32_640_640", "SD_UNet", "mid_down", "conv", "1 32 32 640 640 3 1 1", "UNet middle feature conv proxy"),
    ("unet_conv_16_1280_1280", "SD_UNet", "late_down", "conv", "1 16 16 1280 1280 3 1 1", "UNet late high-channel conv proxy"),
    ("attn_qkv_4096_320_320", "SD_UNet_Attention", "early_attn", "gemm", "4096 320 320", "Attention QKV projection proxy"),
    ("attn_score_1024_64_1024", "SD_UNet_Attention", "mid_attn", "gemm", "1024 64 1024", "Attention score GEMM proxy"),
    ("attn_softmax_1024_1024", "SD_UNet_Attention", "mid_attn", "softmax", "1024 1024", "Attention softmax proxy"),
    ("vae_dec_conv_64_256_128", "VAE_Decoder", "decoder", "conv", "1 64 64 256 128 3 1 1", "VAE decoder conv proxy"),
    ("dit_qkv_256_768_768", "DiT_B4", "transformer", "gemm", "256 768 768", "DiT projection proxy"),
    ("dit_mlp_256_768_3072", "DiT_B4", "transformer_mlp", "gemm", "256 768 3072", "DiT MLP expansion proxy"),
    ("dit_softmax_256_256", "DiT_B4", "transformer_attn", "softmax", "256 256", "DiT attention softmax proxy"),
]


def avg(values):
    return sum(values) / len(values) if values else ""


def parse_log(path):
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
    status = "ok" if ("Simulation Done" in text) else "check"
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
        "status": status,
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
    estimated_compute = base / compute_speedup
    metadata_cycles = base * metadata_ratio
    outlier_cycles = base * outlier_ratio
    flood_cycles = math.ceil((estimated_compute + metadata_cycles + outlier_cycles + switch_cycles) * stall_reduction)
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
        "metadata_cycles": round(metadata_cycles, 2),
        "outlier_cycles": round(outlier_cycles, 2),
        "switch_cycles": switch_cycles,
        "note": "initial FLOOD post-processing estimate; replace assumptions before paper use",
    }


def main():
    LAYER_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for item in WORKLOADS:
        wid, workload, stage, op, shape_args, reason = item
        row = {
            "id": wid,
            "workload": workload,
            "stage": stage,
            "operator": op,
            "shape_args": shape_args,
            "reason": reason,
            "log_file": str(LOG_DIR / f"{wid}.log"),
        }
        row.update(parse_log(Path(row["log_file"])))
        rows.append(row)

    baseline_csv = LAYER_DIR / "workload_baseline_v1.csv"
    with baseline_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    flood_rows = [x for x in (estimate_flood(row) for row in rows) if x]
    flood_csv = LAYER_DIR / "workload_flood_estimate_v1.csv"
    summary_csv = SUMMARY_DIR / "workload_flood_vs_baseline_v1.csv"
    if flood_rows:
        fields = list(flood_rows[0].keys())
        for output in (flood_csv, summary_csv):
            with output.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(flood_rows)

    md = SUMMARY_DIR / "README_workload_v1.md"
    with md.open("w") as f:
        f.write("# FLOOD workload v1 summary\n\n")
        f.write("Representative proxy shapes for SD UNet, VAE Decoder, and DiT. These are not yet full model traces.\n\n")
        for row in flood_rows:
            f.write(
                f"- {row['id']}: baseline {row['baseline_cycles']} cycles, "
                f"FLOOD estimate {row['estimated_flood_cycles']} cycles, "
                f"speedup {row['estimated_speedup']:.3f}x.\n"
            )

    print("wrote", baseline_csv)
    print("wrote", flood_csv)
    print("wrote", summary_csv)
    print("wrote", md)


if __name__ == "__main__":
    main()
