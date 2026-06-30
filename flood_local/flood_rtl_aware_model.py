#!/usr/bin/env python3
"""FLOOD RTL-aware post-processing model.

This model is derived from the visible FLOOD implementation rather than fixed
operator speedup constants. It estimates Conv/GEMM execution with the hardware
parameters in FLOOD/src/main/scala/core/Config.scala:

- 16 tiles
- 32 x 32 CIM core per tile
- 8-bit data
- MACTree tLatency = 4
- 256-bit weight/feature buses
- 512-bit output/joint SRAM buses
- Tile.scala k=1 fast path and k>1 second output transfer
- Cluster.scala RRArbiter serialization of tile outputs

It intentionally does not model outlier bypass or softmax acceleration as
implemented RTL features unless those mechanisms are present in the input data.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

FREQ_MHZ = 940.0


RTL = {
    "row_size": 32,
    "col_size": 32,
    "tile_size": 16,
    "data_width_bits": 8,
    "pipeline": 2,
    "t_latency": 4,
    "weight_bus_bits": 32 * 8,
    "feature_bus_bits": 32 * 8,
    "output_sram_bus_bits": 512,
    "joint_sram_bus_bits": 512,
    "config_bus_bits": 32,
    "max_kernel_block_cout": 32,
    "max_kernel_block_cin": 1024,
    "max_kernel_size": 32,
    "max_pixel_parallel": 32 * 16,
    "frequency_mhz": FREQ_MHZ,
}


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def parse_shape(operator: str, shape_args: str) -> dict[str, int]:
    dims = [int(x) for x in shape_args.split()]
    if operator == "conv":
        if len(dims) != 8:
            raise ValueError(f"conv shape must be B H W I_C O_C K S P, got {shape_args}")
        b, h, w, ic, oc, k, stride, pad = dims
        oh = (h + 2 * pad - k) // stride + 1
        ow = (w + 2 * pad - k) // stride + 1
        return {
            "b": b,
            "h": h,
            "w": w,
            "ic": ic,
            "oc": oc,
            "k": k,
            "stride": stride,
            "pad": pad,
            "oh": oh,
            "ow": ow,
            "m": b * oh * ow,
            "reduction": ic * k * k,
            "n": oc,
        }
    if operator == "gemm":
        if len(dims) != 3:
            raise ValueError(f"gemm shape must be M K N, got {shape_args}")
        m, k, n = dims
        return {"m": m, "reduction": k, "n": n}
    raise ValueError(f"unsupported operator for RTL model: {operator}")


def estimate_operator(operator: str, shape_args: str) -> dict[str, float | int | str]:
    s = parse_shape(operator, shape_args)
    row = RTL["row_size"]
    col = RTL["col_size"]
    tiles = RTL["tile_size"]
    t_latency = RTL["t_latency"]

    # One tile has 32 output lanes, each lane reduces a 32-wide vector through a
    # MACTree over tLatency cycles. 16 tiles process independent pixel/row groups.
    macs_per_cycle = row * col * tiles / t_latency

    m_eff = ceil_div(s["m"], tiles) * tiles
    k_eff = ceil_div(s["reduction"], row) * row
    n_eff = ceil_div(s["n"], col) * col
    useful_macs = s["m"] * s["reduction"] * s["n"]
    padded_macs = m_eff * k_eff * n_eff

    compute_cycles = ceil_div(int(padded_macs), int(macs_per_cycle))
    m_blocks = ceil_div(s["m"], tiles)
    k_blocks = ceil_div(s["reduction"], row)
    n_blocks = ceil_div(s["n"], col)

    # The Tile comments describe output shift-add, per-tile config, and NoC
    # handshakes. These are small for GEMM and visible for spatial convolution.
    pipeline_overhead = (RTL["pipeline"] * t_latency) * max(1, n_blocks)
    config_cycles = 2 * RTL["tile_size"] + n_blocks
    workmode_class = "gemm"
    output_transfer_multiplier = 1
    joint_sram_cycles = 0
    if operator == "conv":
        kernel = s["k"]
        workmode_class = "pointwise_conv" if kernel == 1 else "spatial_conv"
        # Tile.scala stores kernelSize as k-1. kernelSize=0 and workMode=0 is
        # the pointwise fast path: no shift-add and no second output transfer.
        kernel_size_reg = max(0, kernel - 1)
        output_transfer_multiplier = 1 if kernel_size_reg == 0 else 2
        shift_add_cycles = kernel_size_reg * m_blocks * n_blocks
        noc_reduce_cycles = max(0, min(tiles, n_blocks) - 1) * m_blocks
        # OutRouter/MacMachine have 512-bit joint SRAMs for spatial-kernel
        # boundary/joint processing. Keep this as a small explicit term tied to
        # k-1 and output blocks, instead of hiding it in a global multiplier.
        joint_sram_cycles = kernel_size_reg * m_blocks * n_blocks
    else:
        shift_add_cycles = 0
        noc_reduce_cycles = max(0, min(tiles, n_blocks) - 1)

    bytes_per_element = max(1, RTL["data_width_bits"] // 8)
    weight_bytes = s["reduction"] * s["n"] * bytes_per_element
    activation_bytes = s["m"] * s["reduction"] * bytes_per_element
    output_bytes = s["m"] * s["n"] * bytes_per_element
    weight_bus_bytes = RTL["weight_bus_bits"] // 8
    feature_bus_bytes = RTL["feature_bus_bits"] // 8
    output_bus_bytes = RTL["output_sram_bus_bits"] // 8

    weight_load_cycles = ceil_div(weight_bytes, weight_bus_bytes)
    activation_load_cycles = ceil_div(activation_bytes, feature_bus_bytes)
    output_store_cycles = ceil_div(output_bytes, output_bus_bytes)
    # Tile.outputNoc is colSize-wide and Cluster.scala arbitrates 16 tile
    # outputs through one RRArbiter. k>1 transfers both lower and upper halves.
    tile_output_transfer_cycles = m_blocks * n_blocks * output_transfer_multiplier
    active_tiles_per_m_block = min(tiles, max(1, s["m"]))
    output_arbiter_cycles = m_blocks * n_blocks * output_transfer_multiplier * active_tiles_per_m_block

    # The implementation has local SRAMs and ping-pong style buffers, so compute
    # and load are modeled as partially overlapped. Output store is serialized.
    overlapped_main_cycles = max(compute_cycles + pipeline_overhead, weight_load_cycles, activation_load_cycles)
    total_cycles = (
        overlapped_main_cycles
        + output_store_cycles
        + config_cycles
        + shift_add_cycles
        + noc_reduce_cycles
        + tile_output_transfer_cycles
        + output_arbiter_cycles
        + joint_sram_cycles
    )

    utilization = useful_macs / padded_macs if padded_macs else 0.0
    return {
        "rtl_compute_cycles": int(compute_cycles),
        "rtl_weight_load_cycles": int(weight_load_cycles),
        "rtl_activation_load_cycles": int(activation_load_cycles),
        "rtl_output_store_cycles": int(output_store_cycles),
        "rtl_config_cycles": int(config_cycles),
        "rtl_shift_add_cycles": int(shift_add_cycles),
        "rtl_noc_reduce_cycles": int(noc_reduce_cycles),
        "rtl_tile_output_transfer_cycles": int(tile_output_transfer_cycles),
        "rtl_output_arbiter_cycles": int(output_arbiter_cycles),
        "rtl_joint_sram_cycles": int(joint_sram_cycles),
        "rtl_total_cycles": int(total_cycles),
        "rtl_latency_us": total_cycles / FREQ_MHZ,
        "rtl_useful_macs": int(useful_macs),
        "rtl_padded_macs": int(padded_macs),
        "rtl_compute_utilization": utilization,
        "rtl_m_blocks": int(m_blocks),
        "rtl_k_blocks": int(k_blocks),
        "rtl_n_blocks": int(n_blocks),
        "rtl_workmode_class": workmode_class,
        "rtl_output_transfer_multiplier": int(output_transfer_multiplier),
        "rtl_model_note": "derived from FLOOD Config.scala, Tile.scala, Cluster.scala, and MacMachine_top.v; excludes unimplemented outlier/softmax features",
    }


def enrich_row(row: dict[str, str]) -> dict[str, str | int | float]:
    out: dict[str, str | int | float] = dict(row)
    op = row.get("operator", "")
    if op not in {"conv", "gemm"}:
        out["rtl_model_note"] = "operator not supported by current FLOOD RTL-aware model"
        return out
    est = estimate_operator(op, row.get("shape_args", ""))
    out.update(est)
    baseline = float(row.get("total_cycles") or row.get("baseline_cycles") or 0)
    if baseline:
        out["rtl_speedup_vs_pytorchsim_baseline"] = baseline / float(est["rtl_total_cycles"])
    return out


def write_hardware_summary(path: Path):
    lines = [
        "# FLOOD RTL-aware hardware model",
        "source: FLOOD/src/main/scala/core/Config.scala",
        f"frequency_mhz: {FREQ_MHZ}",
        f"tile_size: {RTL['tile_size']}",
        f"cim_core_rows: {RTL['row_size']}",
        f"cim_core_cols: {RTL['col_size']}",
        f"data_width_bits: {RTL['data_width_bits']}",
        f"mactree_pipeline: {RTL['pipeline']}",
        f"mactree_t_latency: {RTL['t_latency']}",
        f"weight_bus_bits: {RTL['weight_bus_bits']}",
        f"feature_bus_bits: {RTL['feature_bus_bits']}",
        f"output_sram_bus_bits: {RTL['output_sram_bus_bits']}",
        f"joint_sram_bus_bits: {RTL['joint_sram_bus_bits']}",
        f"max_kernel_block_cout: {RTL['max_kernel_block_cout']}",
        f"max_kernel_block_cin: {RTL['max_kernel_block_cin']}",
        f"max_pixel_parallel: {RTL['max_pixel_parallel']}",
        "notes:",
        "  - Conv and GEMM are modeled from implemented FLOOD RTL/Chisel parameters.",
        "  - k=1 Conv uses Tile.scala pointwise fast path; k>1 Conv includes shift-add and second output transfer.",
        "  - Cluster.scala RRArbiter output serialization is reported as rtl_output_arbiter_cycles.",
        "  - MacMachine_top.v 512-bit output/joint SRAM width is used for output/joint SRAM terms.",
        "  - Outlier bypass, precision switching, and softmax acceleration are not treated as implemented RTL features here.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Baseline CSV with operator and shape_args columns.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--hardware-out", default="")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with in_path.open(newline="", encoding="utf-8") as f:
        rows = [enrich_row(row) for row in csv.DictReader(f)]

    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if args.hardware_out:
        write_hardware_summary(Path(args.hardware_out))

    print(f"wrote {out_path} with {len(rows)} rows")


if __name__ == "__main__":
    main()
