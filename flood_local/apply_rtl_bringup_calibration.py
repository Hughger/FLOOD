#!/usr/bin/env python3
"""Apply the FLOOD RTL bring-up calibration to workload-level rows.

This is an extrapolation from small Icarus Verilog cases. It maps the existing
backend rows to the MacMachineWrapper testbench parameters:

- rtl_m_blocks -> spatial points
- rtl_k_blocks -> cin_idx_total
- rtl_n_blocks -> cout
- conv kernel -> k
- group_size -> fixed at 4 unless provided
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

FREQ_MHZ = 940.0


def fnum(value: Any) -> float:
    if value in ("", None, "NA"):
        return 0.0
    return float(value)


def fint(value: Any) -> int:
    return int(round(fnum(value)))


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def parse_shape(operator: str, shape_args: str) -> dict[str, int]:
    dims = [int(x) for x in shape_args.split()]
    if operator == "conv":
        b, h, w, ic, oc, k, stride, pad = dims
        oh = (h + 2 * pad - k) // stride + 1
        ow = (w + 2 * pad - k) // stride + 1
        return {"m": b * oh * ow, "reduction": ic * k * k, "n": oc, "k": k}
    if operator == "gemm":
        m, reduction, n = dims
        return {"m": m, "reduction": reduction, "n": n, "k": 1}
    return {"m": 0, "reduction": 0, "n": 0, "k": 1}


def final_run_cycles(k: int, cout: int, group_size: int = 4) -> float:
    k_extra = max(0, k - 1)
    cout_extra = max(0, cout - 1)
    group_extra = max(0, group_size - 4)
    high_group_extra = max(0, group_size - 8)
    return (
        35.0
        + 13.0 * cout_extra
        + 22.0 * k_extra
        + 20.5 * k_extra * cout_extra
        + 1.5 * group_extra
        + 0.375 * high_group_extra
        + 2.75 * k_extra * group_extra
    )


def estimate_row(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = dict(row)
    op = row.get("operator", "")
    if op not in {"conv", "gemm"}:
        out["rtl_bringup_status"] = "unsupported_operator"
        return out

    shape = parse_shape(op, row.get("shape_args", ""))
    m_blocks = fint(row.get("rtl_m_blocks")) or ceil_div(shape["m"], 16)
    cin_idx_total = fint(row.get("rtl_k_blocks")) or ceil_div(shape["reduction"], 32)
    cout = fint(row.get("rtl_n_blocks")) or ceil_div(shape["n"], 32)
    k = shape["k"] if op == "conv" else 1
    group_size = 4

    final_cycles = final_run_cycles(k=k, cout=cout, group_size=group_size)
    nonfinal_cycles = max(0.0, final_cycles - 3.0)
    per_spatial = (cin_idx_total - 1) * nonfinal_cycles + final_cycles
    total = m_blocks * per_spatial
    baseline = fnum(row.get("pytorchsim_cycles") or row.get("total_cycles"))

    out.update(
        {
            "rtl_bringup_k": k,
            "rtl_bringup_cout": cout,
            "rtl_bringup_group_size": group_size,
            "rtl_bringup_cin_idx_total": cin_idx_total,
            "rtl_bringup_spatial_points": m_blocks,
            "rtl_bringup_final_run_cycles": round(final_cycles, 4),
            "rtl_bringup_nonfinal_run_cycles": round(nonfinal_cycles, 4),
            "rtl_bringup_per_spatial_cycles": round(per_spatial, 4),
            "rtl_bringup_total_cycles": round(total, 4),
            "rtl_bringup_latency_us": round(total / FREQ_MHZ, 6),
            "rtl_bringup_speedup_vs_pytorchsim": round(baseline / total, 6) if total and baseline else "",
            "rtl_bringup_status": "extrapolated_from_21_small_rtl_cases",
        }
    )
    if fnum(row.get("rtl_total_cycles")):
        out["rtl_bringup_vs_old_model_ratio"] = round(total / fnum(row.get("rtl_total_cycles")), 6)
    return out


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


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("rtl_bringup_status") != "extrapolated_from_21_small_rtl_cases":
            continue
        key = (str(row.get("dataset")), str(row.get("operator")), str(row.get("rtl_workmode_class")))
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (dataset, op, workmode), items in sorted(groups.items()):
        base = sum(fnum(r.get("pytorchsim_cycles") or r.get("total_cycles")) for r in items)
        old = sum(fnum(r.get("rtl_total_cycles")) for r in items)
        new = sum(fnum(r.get("rtl_bringup_total_cycles")) for r in items)
        out.append(
            {
                "dataset": dataset,
                "operator": op,
                "rtl_workmode_class": workmode,
                "num_rows": len(items),
                "pytorchsim_cycles": round(base, 4),
                "old_rtl_aware_cycles": round(old, 4),
                "rtl_bringup_calibrated_cycles": round(new, 4),
                "speedup_vs_pytorchsim": round(base / new, 6) if new else "",
                "bringup_vs_old_model_ratio": round(new / old, 6) if old else "",
            }
        )
    return out


def write_readme(path: Path, summary: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# RTL Bring-up Calibrated FLOOD Workload Estimate\n\n")
        fh.write("This applies the 21-case Icarus Verilog bring-up calibration to workload-level PyTorchSim rows.\n\n")
        fh.write("Important: this is an extrapolated estimate, not final paper evidence. It should guide the next RTL runs.\n\n")
        fh.write("| dataset | op | workmode | rows | PyTorchSim cycles | calibrated FLOOD cycles | speedup |\n")
        fh.write("|---|---|---|---:|---:|---:|---:|\n")
        for row in summary:
            fh.write(
                f"| {row['dataset']} | {row['operator']} | {row['rtl_workmode_class']} | "
                f"{row['num_rows']} | {row['pytorchsim_cycles']} | "
                f"{row['rtl_bringup_calibrated_cycles']} | {row['speedup_vs_pytorchsim']} |\n"
            )
        fh.write("\nUse this table to choose representative larger RTL validation layers next.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = [estimate_row(r) for r in csv.DictReader(open(args.input, newline="", encoding="utf-8"))]
    summary = summarize(rows)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "rtl_bringup_workload_details.csv", rows)
    write_csv(out_dir / "rtl_bringup_workload_summary.csv", summary)
    write_readme(out_dir / "README.md", summary)
    print(f"wrote RTL bring-up workload estimate to {out_dir}")


if __name__ == "__main__":
    main()
