#!/usr/bin/env python3
"""Apply the group_size=16 multi-Cin v5 rule to workload rows.

This is a projection scenario.  The group=16 multi-Cin path is calibrated by
fixed RTL samples, but group=16 spatial repetition still has an X issue in the
current testbench, so workload-level totals remain calibrated projections.
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


def group16_single_run(cout: int) -> float:
    return 56.0 + 19.0 * max(0, cout - 2)


def group16_multicin_per_spatial(cout: int, cin_idx_total: int) -> tuple[float, str, str]:
    if cin_idx_total <= 1:
        total = group16_single_run(cout)
        return total, str(round(total, 4)), "group16_single_run_v4_validated"
    first = 19.0 * cout + 15.0
    middle = 53.0
    final = 56.0
    cycles = [first] + [middle] * max(0, cin_idx_total - 2) + [final]
    return sum(cycles), ";".join(str(round(x, 4)) for x in cycles), "group16_multicin_v5_validated"


def estimate_row(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = dict(row)
    op = row.get("operator", "")
    if op not in {"conv", "gemm"}:
        out["group16_v5_status"] = "unsupported_operator"
        return out

    shape = parse_shape(op, row.get("shape_args", ""))
    spatial_points = fint(row.get("rtl_m_blocks")) or ceil_div(shape["m"], 16)
    cin_idx_total = fint(row.get("rtl_k_blocks")) or ceil_div(shape["reduction"], 32)
    cout = fint(row.get("rtl_n_blocks")) or ceil_div(shape["n"], 32)
    k = shape["k"] if op == "conv" else 1

    if k != 1:
        status = "projection_uses_group16_v5_for_multicin_but_k3_group16_not_validated"
    else:
        status = "projection_group16_multicin_v5"

    per_spatial, cycle_list, rule_status = group16_multicin_per_spatial(cout, cin_idx_total)
    total = spatial_points * per_spatial
    baseline = fnum(row.get("pytorchsim_cycles") or row.get("total_cycles"))
    old_group4 = fnum(row.get("rtl_bringup_total_cycles"))

    out.update(
        {
            "group16_v5_k": k,
            "group16_v5_cout": cout,
            "group16_v5_group_size": 16,
            "group16_v5_cin_idx_total": cin_idx_total,
            "group16_v5_spatial_points": spatial_points,
            "group16_v5_per_spatial_cycle_list": cycle_list,
            "group16_v5_per_spatial_cycles": round(per_spatial, 4),
            "group16_v5_total_cycles": round(total, 4),
            "group16_v5_latency_us": round(total / FREQ_MHZ, 6),
            "group16_v5_speedup_vs_pytorchsim": round(baseline / total, 6) if total and baseline else "",
            "group16_v5_vs_group4_bringup_ratio": round(total / old_group4, 6) if old_group4 else "",
            "group16_v5_rule_status": rule_status,
            "group16_v5_status": status,
            "group16_v5_note": "calibrated projection; group16 spatial repetition still has RTL X issue",
        }
    )
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
        if not str(row.get("group16_v5_status", "")).startswith("projection"):
            continue
        key = (str(row.get("dataset")), str(row.get("operator")), str(row.get("rtl_workmode_class")))
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (dataset, op, workmode), items in sorted(groups.items()):
        base = sum(fnum(r.get("pytorchsim_cycles") or r.get("total_cycles")) for r in items)
        group4 = sum(fnum(r.get("rtl_bringup_total_cycles")) for r in items)
        group16 = sum(fnum(r.get("group16_v5_total_cycles")) for r in items)
        out.append(
            {
                "dataset": dataset,
                "operator": op,
                "rtl_workmode_class": workmode,
                "num_rows": len(items),
                "pytorchsim_cycles": round(base, 4),
                "group4_bringup_cycles": round(group4, 4),
                "group16_v5_cycles": round(group16, 4),
                "group16_v5_speedup_vs_pytorchsim": round(base / group16, 6) if group16 else "",
                "group16_v5_vs_group4_ratio": round(group16 / group4, 6) if group4 else "",
            }
        )
    return out


def write_readme(path: Path, summary: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD group16 多 Cin v5 workload 投影\n\n")
        fh.write("## 范围\n\n")
        fh.write(
            "本目录把已经通过独立 RTL 样本验证的 `group_size=16` 多 Cin v5 规则应用到 workload 行。"
            "这一步是 `RTL-calibrated projection`，不是完整 workload RTL validation；原因是当前 "
            "`group_size=16` 的空间重复路径仍存在 RTL X 未知态问题。\n\n"
        )
        fh.write("## 规则\n\n")
        fh.write("对 `k=1/group_size=16/res=1` 的多 Cin 情况：\n\n")
        fh.write("```text\n")
        fh.write("first_run = 19*cout + 15\n")
        fh.write("middle_run = 53\n")
        fh.write("final_run = 56\n")
        fh.write("per_spatial = first_run + max(cin_idx_total-2,0)*middle_run + final_run\n")
        fh.write("total = spatial_points * per_spatial\n")
        fh.write("```\n\n")
        fh.write("## 汇总\n\n")
        fh.write(
            "`speedup_vs_pytorchsim` 是 PyTorchSim cycles / FLOOD group16 v5 cycles；小于 1 表示当前"
            "校准后的 FLOOD 投影周期数高于 PyTorchSim baseline。`vs_group4` 是 group16 v5 / group4 bring-up "
            "投影，用来观察不同 FLOOD 分组策略的相对变化。\n\n"
        )
        fh.write("| dataset | op | workmode | rows | PyTorchSim cycles | group4 cycles | group16 v5 cycles | speedup_vs_pytorchsim | vs_group4 |\n")
        fh.write("|---|---|---|---:|---:|---:|---:|---:|---:|\n")
        for row in summary:
            fh.write(
                f"| {row['dataset']} | {row['operator']} | {row['rtl_workmode_class']} | "
                f"{row['num_rows']} | {row['pytorchsim_cycles']} | {row['group4_bringup_cycles']} | "
                f"{row['group16_v5_cycles']} | {row['group16_v5_speedup_vs_pytorchsim']} | "
                f"{row['group16_v5_vs_group4_ratio']} |\n"
            )
        fh.write("\n## 使用边界\n\n")
        fh.write(
            "这张表可以用于指导论文图表和代表性 layer 选择，但论文中应标注为 "
            "`RTL-calibrated projection`。在空间重复路径 X 问题解决前，不应称为完整 workload RTL 验证结果。\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = [estimate_row(r) for r in csv.DictReader(open(args.input, newline="", encoding="utf-8"))]
    summary = summarize(rows)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "group16_v5_workload_details.csv", rows)
    write_csv(out_dir / "group16_v5_workload_summary.csv", summary)
    write_readme(out_dir / "README.md", summary)
    print(f"wrote group16 v5 workload projection to {out_dir}")


if __name__ == "__main__":
    main()
