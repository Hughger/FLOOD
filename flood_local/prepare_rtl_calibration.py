#!/usr/bin/env python3
"""Prepare FLOOD RTL calibration run cases from backend calibration CSV.

The existing FLOOD Verilog testbench is parameterized by small block-level
controls rather than full PyTorchSim shapes. This script maps Conv/GEMM shape
rows into bounded testbench parameters and emits run commands/manifests.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any


ROW_SIZE = 32
COL_SIZE = 32
TILE_SIZE = 16


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def parse_shape(operator: str, shape_args: str) -> dict[str, int]:
    dims = [int(x) for x in shape_args.split()]
    if operator == "conv":
        b, h, w, ic, oc, k, stride, pad = dims
        oh = (h + 2 * pad - k) // stride + 1
        ow = (w + 2 * pad - k) // stride + 1
        return {"b": b, "h": h, "w": w, "ic": ic, "oc": oc, "k": k, "stride": stride, "pad": pad, "oh": oh, "ow": ow}
    if operator == "gemm":
        m, k, n = dims
        return {"m": m, "k": k, "n": n}
    return {}


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def map_case(row: dict[str, str]) -> dict[str, Any]:
    op = row["operator"]
    shape = parse_shape(op, row["shape_args"])
    workmode = row.get("rtl_workmode_class", "")

    if op == "conv":
        k = clamp(shape["k"], 1, 5)
        cout = clamp(ceil_div(shape["oc"], COL_SIZE), 1, 8)
        cin_idx_total = clamp(ceil_div(shape["ic"], ROW_SIZE * 4), 1, 8)
        group_size = 4
        res_cols = clamp(ceil_div(shape["ow"], COL_SIZE), 1, 4)
        # The testbench height is groupNum * RES_ROWS. Keep RTL sim small.
        res_rows = clamp(ceil_div(shape["oh"], TILE_SIZE // group_size), 1, 4)
        stride = clamp(shape["stride"], 1, 4)
        target = "conv"
    elif op == "gemm":
        # Map GEMM to a 1x1-conv-like dense block: M becomes rows/cols, K input
        # channels, N output channels.
        k = 1
        cout = clamp(ceil_div(shape["n"], COL_SIZE), 1, 8)
        cin_idx_total = clamp(ceil_div(shape["k"], ROW_SIZE * 4), 1, 8)
        group_size = 4
        res_cols = clamp(ceil_div(shape["m"], COL_SIZE), 1, 4)
        res_rows = 1
        stride = 1
        target = "gemm_as_1x1"
    else:
        k = cout = cin_idx_total = group_size = res_cols = res_rows = stride = 1
        target = "unsupported"

    plusargs = [
        f"+K={k}",
        f"+COUT={cout}",
        f"+GROUP_SIZE={group_size}",
        f"+CIN_IDX_TOTAL={cin_idx_total}",
        f"+RES_COLS={res_cols}",
        f"+RES_ROWS={res_rows}",
    ]
    defines = [
        f"-DK_PARAM={k}",
        f"-DCOUT_PARAM={cout}",
        f"-DGROUP_SIZE_PARAM={group_size}",
        f"-DGROUP_NUM_PARAM={TILE_SIZE // group_size}",
        f"-DSTRIDE_PARAM={stride}",
        f"-DCIN_IDX_TOTAL={cin_idx_total}",
        f"-DRES_COL_TOTAL={res_cols}",
        f"-DRES_ROW_TOTAL={res_rows}",
    ]

    return {
        "case_id": row["case_id"],
        "dataset": row["dataset"],
        "source_id": row["source_id"],
        "operator": op,
        "shape_args": row["shape_args"],
        "rtl_workmode_class": workmode,
        "rtl_target": target,
        "k": k,
        "cout_blocks": cout,
        "group_size": group_size,
        "group_num": TILE_SIZE // group_size,
        "cin_idx_total": cin_idx_total,
        "res_cols": res_cols,
        "res_rows": res_rows,
        "stride": stride,
        "model_predicted_cycles": row.get("model_predicted_cycles", ""),
        "pytorchsim_cycles": row.get("pytorchsim_cycles", ""),
        "iverilog_defines": " ".join(defines),
        "runtime_plusargs": " ".join(plusargs),
        "notes": "bounded small RTL calibration case derived from PyTorchSim workload shape",
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_readme(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD RTL Calibration Preparation\n\n")
        fh.write("These cases are derived from PyTorchSim workload rows but intentionally bounded for fast RTL simulation.\n\n")
        fh.write("## Recommended Existing RTL Entry\n\n")
        fh.write("- Testbench: `FLOOD/src/test/verilog/testbench_r32c32t16.v`\n")
        fh.write("- Helper SRAM: `FLOOD/src/test/verilog/dpSRAM.v`\n")
        fh.write("- Generated DUT: `MacMachineWrapper.v` from Chisel `GenerateVerilog`\n\n")
        fh.write("## Generated Cases\n\n")
        fh.write("| Case | Op | Workmode | Shape | RTL args |\n")
        fh.write("|---|---|---|---|---|\n")
        for row in rows:
            fh.write(
                f"| {row['case_id']} | {row['operator']} | {row['rtl_workmode_class']} | "
                f"`{row['shape_args']}` | `{row['runtime_plusargs']}` |\n"
            )
        fh.write("\n## Next Step\n\n")
        fh.write("Compile the existing testbench with the matching `iverilog_defines`, run with `runtime_plusargs`, then parse `[INTR] done` time and SRAM/NoC counters from the log. Fill `rtl_sim_cycles` in the original calibration table.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [map_case(row) for row in csv.DictReader(open(args.input, newline="", encoding="utf-8"))]
    write_csv(out_dir / "rtl_calibration_run_matrix.csv", rows)
    write_readme(out_dir / "README.md", rows)
    print(f"wrote RTL calibration preparation to {out_dir}")


if __name__ == "__main__":
    main()
