#!/usr/bin/env python3
"""Generate HPCA test-plan tables from current PyTorchSim/FLOOD outputs.

This is a data-production entry point, not a validation report. It emits the
tables requested by the HPCA test plan. Fields that the current toolchain cannot
produce yet are kept as MISSING with a concrete missing_reason.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


FREQ_MHZ = 940.0


def fnum(value: Any) -> float:
    if value in ("", None, "NA", "MISSING"):
        return 0.0
    return float(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


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


def latency_us(cycles: float) -> float:
    return cycles / FREQ_MHZ


def model_name(row: dict[str, str]) -> str:
    dataset = row.get("dataset", "")
    wid = row.get("id", "")
    if "unet" in wid.lower() or "unet" in dataset.lower() or "trace_" in wid:
        return "SD UNet / synthetic UNet trace"
    if "vae" in wid.lower():
        return "SD VAE"
    if "dit" in wid.lower() or "attn" in wid.lower():
        return "DiT / attention proxy"
    return dataset or "unknown"


def architecture_type(row: dict[str, str]) -> str:
    name = model_name(row)
    if "DiT" in name:
        return "DiT"
    if "VAE" in name or "UNet" in name:
        return "LDM"
    return "unknown"


def source_label(grade: str) -> str:
    if grade.startswith("B_"):
        return "direct RTL-clean + PyTorchSim baseline"
    if grade.startswith("C_"):
        return "RTL-calibrated projection + PyTorchSim baseline"
    if grade.startswith("D_"):
        return "blocked/excluded diagnostic"
    return "unknown"


def aggregate(rows: list[dict[str, str]], config: str) -> dict[str, Any]:
    pytorch = sum(fnum(row.get("pytorchsim_cycles")) for row in rows)
    flood = sum(fnum(row.get("group16_v7_cycles")) for row in rows)
    return {
        "model": "mixed workload subset",
        "config": config,
        "rows": len(rows),
        "latency_cycles": round(flood, 4),
        "latency_us": round(latency_us(flood), 6) if flood else "MISSING",
        "throughput_rows_per_s": round(1_000_000.0 / latency_us(flood), 6) if flood else "MISSING",
        "pytorchsim_baseline_cycles": round(pytorch, 4),
        "speedup_vs_pytorchsim": round(pytorch / flood, 6) if flood else "MISSING",
        "data_source": source_label(rows[0].get("readiness_grade", "")) if rows else "empty",
        "readiness": rows[0].get("readiness_grade", "") if rows else "empty",
    }


def build_e1(main_rows: list[dict[str, str]], appendix_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.append(aggregate(main_rows, "FLOOD direct RTL-clean subset"))
    if appendix_rows:
        rows.append(aggregate(appendix_rows, "FLOOD k3 appendix projection"))
    for row in main_rows + appendix_rows:
        flood = fnum(row.get("group16_v7_cycles"))
        pytorch = fnum(row.get("pytorchsim_cycles"))
        rows.append(
            {
                "model": model_name(row),
                "config": row.get("id"),
                "rows": 1,
                "latency_cycles": round(flood, 4),
                "latency_us": round(latency_us(flood), 6),
                "throughput_rows_per_s": round(1_000_000.0 / latency_us(flood), 6) if flood else "MISSING",
                "pytorchsim_baseline_cycles": round(pytorch, 4),
                "speedup_vs_pytorchsim": round(pytorch / flood, 6) if flood else "MISSING",
                "energy_power": "MISSING",
                "compute_utilization": "MISSING",
                "dram_traffic": "MISSING",
                "sram_traffic": "MISSING",
                "data_source": source_label(row.get("readiness_grade", "")),
                "readiness": row.get("readiness_grade"),
                "missing_reason": "energy/power/utilization/traffic require energy model or simulator counters for this final table",
            }
        )
    return rows


def build_e6(details: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in details:
        rows.append(
            {
                "model": model_name(row),
                "layer_or_workload": row.get("id"),
                "dataflow": row.get("rtl_workmode_class") or row.get("workmode"),
                "bandwidth": "PyTorchSim observed aggregate DRAM GB/s",
                "buffer_size": "MISSING",
                "latency_cycles_pytorchsim": row.get("pytorchsim_cycles"),
                "latency_cycles_flood_projection": row.get("group16_v7_total_cycles"),
                "buffer_usage": "MISSING",
                "stall_cycles": "MISSING",
                "utilization_pytorchsim_systolic_pct": row.get("avg_systolic_util_pct", "MISSING"),
                "dram_read_count": row.get("dram_reads", "MISSING"),
                "dram_write_count": row.get("dram_writes", "MISSING"),
                "data_source": "PyTorchSim counters + FLOOD projection labels",
                "readiness": row.get("group16_v7_adversarial_scope_status", ""),
                "missing_reason": "buffer occupancy/stall cycles require simulator counter export",
            }
        )
    return rows


def sparsity_rows(details: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scenarios = [
        ("no skipping", 0.0, 0.0, 0.0),
        ("zero skipping 25% act", 0.25, 0.0, 0.0),
        ("zero skipping 50% act", 0.50, 0.0, 0.0),
        ("zero skipping 25% act + 25% wt", 0.25, 0.25, 0.0),
        ("+ adder pruning proxy", 0.50, 0.0, 0.10),
        ("+ GCSE group sparsity proxy", 0.50, 0.25, 0.20),
    ]
    for row in details:
        if row.get("operator") not in {"conv", "gemm"}:
            continue
        base_cycles = fnum(row.get("pytorchsim_cycles"))
        flood_cycles = fnum(row.get("group16_v7_total_cycles"))
        macs = fnum(row.get("rtl_useful_macs") or row.get("rtl_padded_macs"))
        for name, act_sp, wt_sp, extra_skip in scenarios:
            combined_skip = 1.0 - (1.0 - act_sp) * (1.0 - wt_sp)
            skipped_mac = min(0.95, combined_skip + extra_skip)
            projected_cycles = flood_cycles * (1.0 - skipped_mac)
            rows.append(
                {
                    "model": model_name(row),
                    "layer_or_workload": row.get("id"),
                    "operator": row.get("operator"),
                    "config": name,
                    "activation_sparsity": round(act_sp, 4),
                    "weight_sparsity": round(wt_sp, 4),
                    "skipped_mac_percent": round(skipped_mac * 100.0, 4),
                    "useful_macs": round(macs, 4),
                    "baseline_cycles": round(flood_cycles, 4),
                    "projected_sparse_cycles": round(projected_cycles, 4),
                    "cycle_reduction_percent": round(skipped_mac * 100.0, 4) if flood_cycles else "MISSING",
                    "energy_reduction_percent": round(skipped_mac * 100.0, 4) if flood_cycles else "MISSING",
                    "utilization_note": "proxy assumes skipped MACs translate linearly to cycle/energy reduction",
                    "data_source": "synthetic sparsity proxy from workload MAC/cycle table",
                    "readiness": row.get("group16_v7_adversarial_scope_status", ""),
                    "missing_reason": "replace proxy sparsity with measured activation/weight sparsity for final paper values",
                }
            )
    return rows


def build_e7_ablation(details: list[dict[str, str]]) -> list[dict[str, Any]]:
    sparse = sparsity_rows(details)
    conv_gemm = [row for row in details if row.get("operator") in {"conv", "gemm"}]
    base_flood_cycles = sum(fnum(row.get("group16_v7_total_cycles")) for row in conv_gemm)
    softmax_proxy_cycles = sum(length * 12.0 + 96.0 for length in [32, 64, 128, 256, 512, 1024, 2048]) * 0.28
    configs = [
        ("Base", "no skipping"),
        ("+ zero skipping", "zero skipping 50% act"),
        ("+ adder pruning", "+ adder pruning proxy"),
        ("+ GCSE", "+ GCSE group sparsity proxy"),
        ("+ INT8/INT4 mixed", "quant proxy"),
        ("+ outlier bypass", "outlier proxy"),
        ("+ Softmax", "softmax proxy"),
        ("+ FLOOD/PLANE dataflow", "dataflow proxy"),
        ("Full FLOOD", "full proxy"),
    ]
    rows: list[dict[str, Any]] = []
    for label, source_config in configs:
        if source_config == "quant proxy":
            latency = base_flood_cycles * 0.52
            rows.append(
                {
                    "config": label,
                    "latency_cycles": round(latency, 4),
                    "energy": "proxy 58.0% bit-width storage reduction",
                    "utilization": "proxy",
                    "memory_traffic": "proxy",
                    "quality_drop": "MISSING",
                    "data_source": "E3 mixed-precision proxy",
                    "missing_reason": "replace proxy with quantized workload runner and quality metrics before final paper values",
                }
            )
            continue
        if source_config == "outlier proxy":
            latency = base_flood_cycles * 1.005
            rows.append(
                {
                    "config": label,
                    "latency_cycles": round(latency, 4),
                    "energy": "proxy 1.0% power overhead",
                    "utilization": "proxy",
                    "memory_traffic": "MISSING",
                    "quality_drop": "MISSING",
                    "data_source": "E4 0.5% outlier-bypass proxy",
                    "missing_reason": "replace proxy with measured outlier ratio and quality recovery",
                }
            )
            continue
        if source_config == "softmax proxy":
            rows.append(
                {
                    "config": label,
                    "latency_cycles": round(softmax_proxy_cycles, 4),
                    "energy": "MISSING",
                    "utilization": "proxy",
                    "memory_traffic": "MISSING",
                    "quality_drop": "MISSING",
                    "data_source": "E5 online/streaming softmax proxy",
                    "missing_reason": "replace proxy with RTL/numerical softmax runner before final paper values",
                }
            )
            continue
        if source_config == "dataflow proxy":
            rows.append(
                {
                    "config": label,
                    "latency_cycles": round(base_flood_cycles, 4),
                    "energy": "MISSING",
                    "utilization": "proxy",
                    "memory_traffic": "PyTorchSim counter-derived in E6",
                    "quality_drop": "MISSING",
                    "data_source": "current FLOOD RTL-aware group16 mapping",
                    "missing_reason": "replace proxy with exported buffer/stall/dataflow counters for final paper values",
                }
            )
            continue
        if source_config == "full proxy":
            latency = base_flood_cycles * 0.175 * 0.52 * 1.005 + softmax_proxy_cycles
            rows.append(
                {
                    "config": label,
                    "latency_cycles": round(latency, 4),
                    "energy": "proxy composite",
                    "utilization": "proxy",
                    "memory_traffic": "proxy",
                    "quality_drop": "MISSING",
                    "data_source": "composite of E2/E3/E4/E5 proxies",
                    "missing_reason": "only a table-production placeholder; final paper requires measured integrated runner",
                }
            )
            continue
        if source_config is None:
            rows.append(
                {
                    "config": label,
                    "latency_cycles": "MISSING",
                    "energy": "MISSING",
                    "utilization": "MISSING",
                    "memory_traffic": "MISSING",
                    "quality_drop": "MISSING",
                    "data_source": "not generated yet",
                    "missing_reason": "requires quant/outlier/softmax/dataflow/full-system runner",
                }
            )
            continue
        items = [row for row in sparse if row["config"] == source_config]
        baseline = sum(fnum(row["baseline_cycles"]) for row in items)
        latency = sum(fnum(row["projected_sparse_cycles"]) for row in items)
        reduction = (1.0 - latency / baseline) * 100.0 if baseline else 0.0
        rows.append(
            {
                "config": label,
                "latency_cycles": round(latency, 4),
                "energy": f"proxy {round(reduction, 4)}% reduction",
                "utilization": "proxy",
                "memory_traffic": "MISSING",
                "quality_drop": "MISSING",
                "data_source": "synthetic sparsity proxy from workload MAC/cycle table",
                "missing_reason": "replace proxy with measured mechanism runner for final paper values",
            }
        )
    return rows


def build_e3_quantization(details: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    configs = [
        ("FP16", 16.0, 1.00, "reference"),
        ("INT8 all", 8.0, 0.62, "proxy"),
        ("INT4 all", 4.0, 0.38, "proxy"),
        ("30% INT4 mixed", 6.8, 0.52, "proxy"),
        ("sensitivity-based mixed", 7.2, 0.50, "proxy"),
    ]
    groups: dict[str, list[dict[str, str]]] = {}
    for row in details:
        if row.get("operator") in {"conv", "gemm"}:
            groups.setdefault(model_name(row), []).append(row)
    for model, items in sorted(groups.items()):
        base_cycles = sum(fnum(row.get("group16_v7_total_cycles")) for row in items)
        base_mem = sum(fnum(row.get("rtl_padded_macs") or row.get("rtl_useful_macs")) for row in items) * 2.0
        for config, bits, latency_scale, source in configs:
            latency = base_cycles * latency_scale
            peak_mem = base_mem * bits / 16.0
            rows.append(
                {
                    "model": model,
                    "precision_config": config,
                    "throughput_rows_per_s": round(1_000_000.0 / latency_us(latency), 6) if latency else "MISSING",
                    "peak_memory_proxy_bytes": round(peak_mem, 4),
                    "latency_cycles": round(latency, 4),
                    "fid": "MISSING",
                    "psnr": "MISSING",
                    "ssim": "MISSING",
                    "lpips": "MISSING",
                    "clip_score": "MISSING",
                    "data_source": f"{source} quantization scaling from workload cycles/MACs",
                    "missing_reason": "replace proxy latency/memory and fill quality metrics with quantization runner outputs",
                }
            )
    return rows


def build_e4_outlier(details: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    configs = [
        ("INT8 truncation", 0.0, 0.0, 0.0, 0.0),
        ("+ outlier bypass 0.1%", 0.001, 0.005, 0.003, 0.001),
        ("+ outlier bypass 0.5%", 0.005, 0.020, 0.010, 0.005),
        ("+ outlier bypass 1.0%", 0.010, 0.040, 0.020, 0.010),
        ("wide-MAC baseline proxy", 1.0, 0.250, 0.180, 0.000),
    ]
    groups: dict[str, list[dict[str, str]]] = {}
    for row in details:
        if row.get("operator") in {"conv", "gemm"}:
            groups.setdefault(model_name(row), []).append(row)
    for model, items in sorted(groups.items()):
        base_cycles = sum(fnum(row.get("group16_v7_total_cycles")) for row in items)
        for config, ratio, area_overhead, power_overhead, cycle_overhead in configs:
            rows.append(
                {
                    "model": model,
                    "config": config,
                    "outlier_ratio": round(ratio, 6),
                    "psnr": "MISSING",
                    "ssim": "MISSING",
                    "lpips": "MISSING",
                    "extra_area_percent": round(area_overhead * 100.0, 4),
                    "extra_power_percent": round(power_overhead * 100.0, 4),
                    "extra_cycles": round(base_cycles * cycle_overhead, 4),
                    "data_source": "outlier bypass proxy from configured outlier ratio",
                    "missing_reason": "replace proxy with measured outlier ratio and quality recovery",
                }
            )
    return rows


def build_e5_softmax(details: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lengths = sorted(
        {
            int(fnum(row.get("N") or row.get("seq_len") or 0))
            for row in details
            if row.get("operator") in {"softmax", "attention", "matmul"} and fnum(row.get("N") or row.get("seq_len") or 0) > 0
        }
    )
    if not lengths:
        lengths = [32, 64, 128, 256, 512, 1024, 2048]
    configs = [
        ("FP32 reference softmax", 1.00, 0.00, "reference"),
        ("INT8 LUT softmax proxy", 0.42, 0.02, "proxy"),
        ("piecewise-linear softmax proxy", 0.35, 0.04, "proxy"),
        ("online/streaming softmax proxy", 0.28, 0.01, "proxy"),
    ]
    for length in lengths:
        base_cycles = length * 12.0 + 96.0
        for config, latency_scale, approx_error, source in configs:
            cycles = base_cycles * latency_scale
            rows.append(
                {
                    "model": "DiT / attention proxy" if length >= 256 else "attention microbenchmark",
                    "vector_length": length,
                    "implementation": config,
                    "latency_cycles": round(cycles, 4),
                    "latency_us": round(latency_us(cycles), 6),
                    "speedup_vs_fp32_reference": round(base_cycles / cycles, 6) if cycles else "MISSING",
                    "approximation_error_proxy": round(approx_error, 6),
                    "accuracy_drop": "MISSING",
                    "area": "MISSING",
                    "power": "MISSING",
                    "data_source": f"{source} softmax micro-model from vector length",
                    "missing_reason": "replace proxy latency/error with RTL or numerical softmax runner outputs before final paper claims",
                }
            )
    return rows


def build_e8(rows_in: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows_in:
        key = (model_name(row), architecture_type(row), row.get("readiness_grade", ""))
        groups.setdefault(key, []).append(row)
    rows: list[dict[str, Any]] = []
    for (model, arch, readiness), items in sorted(groups.items()):
        flood = sum(fnum(row.get("group16_v7_cycles")) for row in items)
        pytorch = sum(fnum(row.get("pytorchsim_cycles")) for row in items)
        rows.append(
            {
                "model": model,
                "architecture_type": arch,
                "config": readiness,
                "rows": len(items),
                "throughput_rows_per_s": round(1_000_000.0 / latency_us(flood), 6) if flood else "MISSING",
                "latency_cycles": round(flood, 4),
                "latency_us": round(latency_us(flood), 6) if flood else "MISSING",
                "energy": "MISSING",
                "psnr_ssim": "MISSING",
                "generation_quality": "MISSING",
                "speedup_vs_pytorchsim": round(pytorch / flood, 6) if flood else "MISSING",
                "data_source": source_label(readiness),
                "missing_reason": "quality and energy metrics require image-quality and energy runners",
            }
        )
    return rows


def build_e9() -> list[dict[str, Any]]:
    return [
        {
            "baseline": "Base FLOOD",
            "process": "MISSING",
            "frequency": f"{FREQ_MHZ} MHz for current RTL cycle conversion",
            "area": "MISSING",
            "precision": "INT-like RTL datapath / exact precision to be confirmed",
            "buffer": "MISSING",
            "bandwidth": "from PyTorchSim per-row counters when available",
            "sparsity_support": "not enabled in current generated tables",
            "dataflow": "FLOOD RTL-aware mapping",
            "softmax": "E5 proxy table generated; RTL/numerical runner pending",
            "outlier": "E4 proxy table generated; measured outlier runner pending",
            "mapping": "group16 k1/k3 calibrated projection + direct RTL-clean gate",
            "data_source": "repo scripts and readiness gates",
        },
        {
            "baseline": "Full FLOOD",
            "process": "MISSING",
            "frequency": f"{FREQ_MHZ} MHz for current RTL cycle conversion",
            "area": "MISSING",
            "precision": "MISSING",
            "buffer": "MISSING",
            "bandwidth": "MISSING",
            "sparsity_support": "MISSING",
            "dataflow": "MISSING",
            "softmax": "MISSING",
            "outlier": "MISSING",
            "mapping": "requires E2/E3/E4/E5/E6 completion",
            "data_source": "not yet complete",
        },
    ]


def missing_table(experiment: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "experiment": experiment,
            "status": "MISSING",
            "required_runner": runner,
            "output_expected": output,
            "note": note,
        }
        for runner, output, note in rows
    ]


def write_readme(out_dir: Path) -> None:
    with (out_dir / "README.md").open("w", encoding="utf-8") as fh:
        fh.write("# HPCA experiment tables v1\n\n")
        fh.write("This directory is the current paper-data production output. It maps existing PyTorchSim/FLOOD data into the E1-E9 tables from the HPCA test plan.\n\n")
        fh.write("## One-command generation\n\n")
        fh.write("Run the full paper-data pipeline:\n\n")
        fh.write("```powershell\n")
        fh.write("powershell -ExecutionPolicy Bypass -File flood_local\\run_hpca_paper_data_pipeline.ps1\n")
        fh.write("```\n\n")
        fh.write("Regenerate only these final E1-E9 tables from existing gates:\n\n")
        fh.write("```powershell\n")
        fh.write("powershell -ExecutionPolicy Bypass -File flood_local\\run_hpca_experiment_tables.ps1\n")
        fh.write("```\n\n")
        fh.write("## Generated tables\n\n")
        for name in [
            "E1_end_to_end_main_results.csv",
            "E2_sparsity_proxy.csv",
            "E3_quantization_proxy.csv",
            "E4_outlier_proxy.csv",
            "E5_softmax_proxy.csv",
            "E6_dataflow_storage.csv",
            "E7_ablation_proxy.csv",
            "E8_diffusion_family.csv",
            "E9_baseline_fairness.csv",
        ]:
            fh.write(f"- `{name}`\n")
        fh.write("\n## Rule\n\n")
        fh.write("Values are generated only when the current toolchain has the data. Unknown paper metrics are marked MISSING rather than guessed.\n")
        fh.write("\n## Current proxy tables\n\n")
        fh.write("- `E2_sparsity_proxy.csv` is generated from synthetic sparsity assumptions and workload MAC/cycle counts. It has the final table schema, but final paper values should replace proxy sparsity with measured activation/weight sparsity.\n")
        fh.write("- `E3_quantization_proxy.csv` estimates latency and peak-memory scaling from bit width. Quality metrics remain MISSING until the quantization quality runner is integrated.\n")
        fh.write("- `E4_outlier_proxy.csv` estimates outlier bypass overhead from configured outlier ratios. Quality recovery remains MISSING until outlier quality experiments are integrated.\n")
        fh.write("- `E5_softmax_proxy.csv` estimates softmax latency and approximation error from vector length. It must be replaced by an RTL/numerical softmax runner for final paper claims.\n")
        fh.write("- `E7_ablation_proxy.csv` reuses E2/E3/E4/E5 proxies and current dataflow labels to produce a complete ablation-table skeleton. Final paper values require measured integrated runners.\n")
        fh.write("\n## How others should use it\n\n")
        fh.write("1. Update the upstream workload CSVs or run new experiments.\n")
        fh.write("2. Run `flood_local/run_hpca_paper_data_pipeline.ps1`.\n")
        fh.write("3. Fill paper tables only from the generated E1-E9 CSV files.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate-dir", required=True)
    parser.add_argument("--workload-details", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    gate = Path(args.gate_dir)
    main_rows = read_csv(gate / "main_table_rows.csv")
    appendix_rows = read_csv(gate / "appendix_projection_rows.csv")
    blocked_rows = read_csv(gate / "blocked_or_excluded_rows.csv")
    all_readiness = main_rows + appendix_rows + blocked_rows
    details = read_csv(Path(args.workload_details))

    out_dir = Path(args.out_dir)
    stale = out_dir / "E2_sparsity_missing.csv"
    if stale.exists():
        stale.unlink()
    write_csv(out_dir / "E1_end_to_end_main_results.csv", build_e1(main_rows, appendix_rows))
    write_csv(out_dir / "E2_sparsity_proxy.csv", sparsity_rows(details))
    stale_e3 = out_dir / "E3_quantization_missing.csv"
    if stale_e3.exists():
        stale_e3.unlink()
    write_csv(out_dir / "E3_quantization_proxy.csv", build_e3_quantization(details))
    stale_e4 = out_dir / "E4_outlier_missing.csv"
    if stale_e4.exists():
        stale_e4.unlink()
    write_csv(out_dir / "E4_outlier_proxy.csv", build_e4_outlier(details))
    stale_e5 = out_dir / "E5_softmax_missing.csv"
    if stale_e5.exists():
        stale_e5.unlink()
    write_csv(out_dir / "E5_softmax_proxy.csv", build_e5_softmax(details))
    write_csv(out_dir / "E6_dataflow_storage.csv", build_e6(details))
    stale_e7 = out_dir / "E7_ablation_missing.csv"
    if stale_e7.exists():
        stale_e7.unlink()
    write_csv(out_dir / "E7_ablation_proxy.csv", build_e7_ablation(details))
    write_csv(out_dir / "E8_diffusion_family.csv", build_e8(all_readiness))
    write_csv(out_dir / "E9_baseline_fairness.csv", build_e9())
    write_readme(out_dir)
    print(f"wrote HPCA experiment tables to {out_dir}")


if __name__ == "__main__":
    main()
