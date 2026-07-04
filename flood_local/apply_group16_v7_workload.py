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

DIRECT_CLEAN_WORKLOAD_IDS = {
    "trace_gemm_001",
    "trace_gemm_005",
    "trace_gemm_002",
    "trace_conv_013",
    "trace_gemm_014",
    "trace_gemm_015",
}

DIRECT_BLOCKED_WORKLOAD_IDS = {
    "attn_score_1024_64_1024",
    "trace_conv_018",
    "trace_gemm_016",
}


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


def k1_total(cout: int, cin: int, spatial_points: int) -> tuple[float, float, str, str]:
    """Return workload total with spatial reuse observed in direct RTL rows.

    The first spatial block pays the Cout-dependent startup cost. Later spatial
    blocks reuse the same lower-cost nonfinal/final sequence. This is invisible
    for cout=2, which is why the earlier per-spatial multiplier passed small
    direct-clean rows but overestimated wider Cout workload rows.
    """
    spatial_points = max(1, spatial_points)
    if cin <= 1:
        first = 56.0 + 19.0 * max(0, cout - 2)
        repeat = 56.0
        total = first + max(0, spatial_points - 1) * repeat
        desc = f"first_spatial={round(first, 4)};repeat_spatial={round(repeat, 4)};spatial_points={spatial_points}"
        return total, total / spatial_points, desc, "k1_group16_spatial_reuse_v8"

    first = (19.0 * cout + 15.0) + 53.0 * max(0, cin - 2) + 56.0
    repeat = 53.0 * max(0, cin - 1) + 56.0
    total = first + max(0, spatial_points - 1) * repeat
    desc = f"first_spatial={round(first, 4)};repeat_spatial={round(repeat, 4)};spatial_points={spatial_points}"
    return total, total / spatial_points, desc, "k1_group16_spatial_reuse_v8"


def k3_per_spatial(cout: int, cin: int) -> tuple[float, str, str]:
    final = 147.0 * cout + 38.0
    nonfinal = final - 3.0
    cycles = [nonfinal] * max(0, cin - 1) + [final]
    return sum(cycles), ";".join(str(round(x, 4)) for x in cycles), "k3_group16_v7"


def adversarial_scope_status(row: dict[str, str], k: int, cin: int, spatial_points: int) -> tuple[str, str]:
    wid = row.get("id", "")
    workmode = row.get("rtl_workmode_class", "")
    if wid in DIRECT_CLEAN_WORKLOAD_IDS:
        return "B_direct_rtl_clean_workload_row", "exact workload row directly RTL-clean; projection matched direct RTL"
    if wid in DIRECT_BLOCKED_WORKLOAD_IDS:
        return "D_direct_rtl_blocked", "direct RTL attempt observed Cluster/Router/Output X; invalid as clean workload evidence"
    if k == 1 and cin >= 3 and spatial_points >= 16:
        return "D_observed_multicin_spatial_x_boundary", (
            "boundary probe found cout=2/cin=3/spatial=16 completes with matching cycles but Cluster/Router/Output X"
        )
    if k == 1 and cin >= 2 and spatial_points >= 2 and fint(row.get("group16_v5_cout")) >= 29:
        return "D_observed_high_cout_multicin_boundary", (
            "adversarial scan found cout=29/cin=2/res_cols=2 reaches 0-cycle boundary even at res_rows=1"
        )
    if k == 1 and workmode in {"gemm", "pointwise_conv"}:
        if spatial_points > 16:
            return "C_projection_large_spatial_extent_unvalidated", "large spatial extent exceeds direct-clean workload range"
        return "C_projection_small_extent_not_directly_run", "formula-supported but this exact workload row was not directly RTL-run"
    if k == 3:
        if spatial_points > 16 or cin > 3:
            return "C_projection_large_k3_extent_unvalidated", "k3 rule-supported but workload extent exceeds direct-clean holdout range"
        return "C_projection_k3_not_directly_run", "k3 rule-supported but this exact workload row was not directly RTL-run"
    return "C_projection_unclassified", "projection requires more direct RTL evidence"


def estimate(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = dict(row)
    op = row.get("operator", "")
    if op not in {"conv", "gemm"}:
        out["group16_v7_status"] = "unsupported_operator"
        out["group16_v7_adversarial_scope_status"] = "D_excluded"
        out["group16_v7_adversarial_scope_note"] = "operator not supported by current FLOOD RTL model"
        return out

    k = fint(row.get("group16_v5_k"))
    cout = fint(row.get("group16_v5_cout"))
    cin = fint(row.get("group16_v5_cin_idx_total"))
    spatial_points = fint(row.get("group16_v5_spatial_points"))
    if k == 1:
        total, per_spatial, cycle_list, rule = k1_total(cout, cin, spatial_points)
        status = "projection_from_k1_group16_v5_v6"
    elif k == 3:
        per_spatial, cycle_list, rule = k3_per_spatial(cout, cin)
        total = spatial_points * per_spatial
        status = "projection_from_k3_group16_v7"
    else:
        out["group16_v7_status"] = "unsupported_kernel"
        out["group16_v7_adversarial_scope_status"] = "D_excluded"
        out["group16_v7_adversarial_scope_note"] = "kernel not supported by current group16 v7 simulator"
        return out

    scope_status, scope_note = adversarial_scope_status(row, k, cin, spatial_points)
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
            "group16_v7_adversarial_scope_status": scope_status,
            "group16_v7_adversarial_scope_note": scope_note,
            "group16_v7_note": "RTL-calibrated projection; full workload RTL validation not claimed",
        }
    )
    return out


def summarize_by_scope(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        status = str(row.get("group16_v7_adversarial_scope_status") or row.get("group16_v7_status") or "unknown")
        groups.setdefault(status, []).append(row)
    out: list[dict[str, Any]] = []
    for status, items in sorted(groups.items()):
        out.append(
            {
                "group16_v7_adversarial_scope_status": status,
                "num_rows": len(items),
                "pytorchsim_cycles": round(sum(fnum(r.get("pytorchsim_cycles")) for r in items), 4),
                "group16_v7_cycles": round(sum(fnum(r.get("group16_v7_total_cycles")) for r in items), 4),
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


def write_readme(path: Path, summary: list[dict[str, Any]], scope_summary: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD group16 v7 workload 投影\n\n")
        fh.write("## 范围\n\n")
        fh.write(
            "本目录把 `k=1` 的 v5/v6 规则和 `k=3` 的 v7 规则应用到 workload。"
            "这是 RTL-calibrated projection，不是完整 workload RTL validation。\n\n"
        )
        fh.write("## 规则\n\n")
        fh.write("```text\n")
        fh.write("k=1: v8 spatial-reuse rule derived from direct workload RTL rows\n")
        fh.write("k=3: final_run=147*cout+38; nonfinal_run=final_run-3\n")
        fh.write("k=1 total = first_spatial + (spatial_points-1)*repeat_spatial\n")
        fh.write("k=3 total = spatial_points * per_spatial_cycles\n")
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
        fh.write("\n## 对抗性审查分级\n\n")
        fh.write("| scope status | rows | PyTorchSim cycles | group16 v7 cycles |\n")
        fh.write("|---|---:|---:|---:|\n")
        for row in scope_summary:
            fh.write(
                f"| {row['group16_v7_adversarial_scope_status']} | {row['num_rows']} | "
                f"{row['pytorchsim_cycles']} | {row['group16_v7_cycles']} |\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = [estimate(row) for row in csv.DictReader(open(args.input, newline="", encoding="utf-8"))]
    summary = summarize(rows)
    scope_summary = summarize_by_scope(rows)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "group16_v7_workload_details.csv", rows)
    write_csv(out_dir / "group16_v7_workload_summary.csv", summary)
    write_csv(out_dir / "group16_v7_workload_scope_summary.csv", scope_summary)
    write_readme(out_dir / "README.md", summary, scope_summary)
    print(f"wrote group16 v7 workload projection to {out_dir}")


if __name__ == "__main__":
    main()
