#!/usr/bin/env python3
"""Apply group16 v5/v7 RTL-clean rules to workload rows.

v5 covers k=1 multi-Cin. v7 adds k=3/group16/res=1 evidence. Workload totals
remain calibrated projections because large spatial repetition is not full RTL.
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


def k1_per_spatial(cout: int, cin: int) -> tuple[float, str, str]:
    if cin <= 1:
        total = 56.0 + 19.0 * max(0, cout - 2)
        return total, str(round(total, 4)), "k1_group16_single_run_v4_v6"
    first = 19.0 * cout + 15.0
    middle = 53.0
    final = 56.0
    cycles = [first] + [middle] * max(0, cin - 2) + [final]
    return sum(cycles), ";".join(str(round(x, 4)) for x in cycles), "k1_group16_multicin_v5"


def k3_per_spatial(cout: int, cin: int) -> tuple[float, str, str]:
    final = 147.0 * cout + 38.0
    nonfinal = final - 3.0
    cycles = [nonfinal] * max(0, cin - 1) + [final]
    return sum(cycles), ";".join(str(round(x, 4)) for x in cycles), "k3_group16_v7"


def estimate(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = dict(row)
    op = row.get("operator", "")
    if op not in {"conv", "gemm"}:
        out["group16_v7_status"] = "unsupported_operator"
        return out

    k = fint(row.get("group16_v5_k"))
    cout = fint(row.get("group16_v5_cout"))
    cin = fint(row.get("group16_v5_cin_idx_total"))
    spatial_points = fint(row.get("group16_v5_spatial_points"))
    if k == 1:
        per_spatial, cycle_list, rule = k1_per_spatial(cout, cin)
        status = "projection_from_k1_group16_v5_v6"
    elif k == 3:
        per_spatial, cycle_list, rule = k3_per_spatial(cout, cin)
        status = "projection_from_k3_group16_v7"
    else:
        out["group16_v7_status"] = "unsupported_kernel"
        return out

    total = spatial_points * per_spatial
    baseline = fnum(row.get("pytorchsim_cycles"))
    group4 = fnum(row.get("rtl_bringup_total_cycles"))
    out.update(
        {
            "group16_v7_k": k,
            "group16_v7_cout": cout,
            "group16_v7_cin_idx_total": cin,
            "group16_v7_spatial_points": spatial_points,
            "group16_v7_per_spatial_cycle_list": cycle_list,
            "group16_v7_per_spatial_cycles": round(per_spatial, 4),
            "group16_v7_total_cycles": round(total, 4),
            "group16_v7_latency_us": round(total / FREQ_MHZ, 6),
            "group16_v7_speedup_vs_pytorchsim": round(baseline / total, 6) if total and baseline else "",
            "group16_v7_vs_group4_bringup_ratio": round(total / group4, 6) if group4 else "",
            "group16_v7_rule_status": rule,
            "group16_v7_status": status,
            "group16_v7_note": "RTL-calibrated projection; full workload RTL validation not claimed",
        }
    )
    return out


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if not str(row.get("group16_v7_status", "")).startswith("projection"):
            continue
        key = (str(row.get("dataset")), str(row.get("operator")), str(row.get("rtl_workmode_class")))
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (dataset, op, workmode), items in sorted(groups.items()):
        base = sum(fnum(r.get("pytorchsim_cycles")) for r in items)
        group4 = sum(fnum(r.get("rtl_bringup_total_cycles")) for r in items)
        group16 = sum(fnum(r.get("group16_v7_total_cycles")) for r in items)
        out.append(
            {
                "dataset": dataset,
                "operator": op,
                "rtl_workmode_class": workmode,
                "num_rows": len(items),
                "pytorchsim_cycles": round(base, 4),
                "group4_bringup_cycles": round(group4, 4),
                "group16_v7_cycles": round(group16, 4),
                "group16_v7_speedup_vs_pytorchsim": round(base / group16, 6) if group16 else "",
                "group16_v7_vs_group4_ratio": round(group16 / group4, 6) if group4 else "",
            }
        )
    return out


def write_readme(path: Path, summary: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD group16 v7 workload 投影\n\n")
        fh.write("## 范围\n\n")
        fh.write(
            "本目录把 `k=1` 的 v5/v6 规则和 `k=3` 的 v7 规则应用到 workload。"
            "这是 RTL-calibrated projection，不是完整 workload RTL validation。\n\n"
        )
        fh.write("## 规则\n\n")
        fh.write("```text\n")
        fh.write("k=1: v5 multi-Cin rule\n")
        fh.write("k=3: final_run=147*cout+38; nonfinal_run=final_run-3\n")
        fh.write("total = spatial_points * per_spatial_cycles\n")
        fh.write("```\n\n")
        fh.write("## 汇总\n\n")
        fh.write("| dataset | op | workmode | rows | PyTorchSim cycles | group4 cycles | group16 v7 cycles | speedup_vs_pytorchsim | vs_group4 |\n")
        fh.write("|---|---|---|---:|---:|---:|---:|---:|---:|\n")
        for row in summary:
            fh.write(
                f"| {row['dataset']} | {row['operator']} | {row['rtl_workmode_class']} | {row['num_rows']} | "
                f"{row['pytorchsim_cycles']} | {row['group4_bringup_cycles']} | {row['group16_v7_cycles']} | "
                f"{row['group16_v7_speedup_vs_pytorchsim']} | {row['group16_v7_vs_group4_ratio']} |\n"
            )
        fh.write("\n## 使用边界\n\n")
        fh.write(
            "k3 v7 已有小规模 fitting/holdout RTL-clean 证据，但 workload 的大空间点数和大 Cin 仍是外推。"
            "论文中应标注为 RTL-calibrated projection。\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = [estimate(row) for row in csv.DictReader(open(args.input, newline="", encoding="utf-8"))]
    summary = summarize(rows)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "group16_v7_workload_details.csv", rows)
    write_csv(out_dir / "group16_v7_workload_summary.csv", summary)
    write_readme(out_dir / "README.md", summary)
    print(f"wrote group16 v7 workload projection to {out_dir}")


if __name__ == "__main__":
    main()
