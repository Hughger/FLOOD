#!/usr/bin/env python3
"""Build a paper data readiness package from current FLOOD RTL evidence."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


def fnum(value: Any) -> float:
    if value in ("", None, "NA"):
        return 0.0
    return float(value)


def fint(value: Any) -> int:
    return int(round(fnum(value)))


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
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
    "trace_gemm_007",
    "trace_gemm_008",
    "trace_gemm_016",
}


def workload_grade(row: dict[str, str]) -> tuple[str, str]:
    op = row.get("operator", "")
    if op not in {"conv", "gemm"}:
        return "D_excluded", "operator_not_supported_by_current_flood_rtl_model"

    k = fint(row.get("group16_v5_k"))
    cin = fint(row.get("group16_v5_cin_idx_total"))
    spatial_points = fint(row.get("group16_v5_spatial_points"))
    workmode = row.get("rtl_workmode_class", "")
    wid = row.get("id", "")

    if wid in DIRECT_BLOCKED_WORKLOAD_IDS:
        return "D_direct_rtl_blocked", (
            "direct RTL attempt observed Cluster/Router/Output X; invalid as clean workload evidence"
        )

    if wid in DIRECT_CLEAN_WORKLOAD_IDS:
        return "B_direct_rtl_clean_workload_row", (
            "this exact workload row was directly RTL-clean and matched v7 projection"
        )

    if k == 1 and cin >= 3 and spatial_points >= 16:
        return "D_observed_multicin_spatial_x_boundary", (
            "boundary probe found cout=2/cin=3/spatial=16 completes with matching cycles but Cluster/Router/Output X"
        )

    if k == 1 and cin >= 2 and spatial_points >= 64:
        return "D_observed_large_spatial_x_boundary", (
            "direct probe found cout=2/cin=2/spatial=64 completes with matching cycles but Cluster/Router/Output X"
        )

    if k == 1 and cin >= 2 and spatial_points >= 2 and fint(row.get("group16_v5_cout")) >= 29:
        return "D_observed_high_cout_multicin_boundary", (
            "adversarial scan found cout=29/cin=2/res_cols=2 reaches 0-cycle boundary even at res_rows=1"
        )

    if k == 1 and workmode in {"gemm", "pointwise_conv"} and cin >= 1:
        if spatial_points > 16:
            return "C_projection_large_spatial_extent_unvalidated", (
                "uses k1/group16 rule, but direct RTL validation showed large spatial extent can fail"
            )
        return "C_projection_small_extent_not_directly_run", (
            "uses validated k1/group16 rule but this exact row was not directly RTL-run"
        )
    if k == 3:
        if spatial_points > 16 or cin > 3:
            return "C_projection_large_k3_extent_unvalidated", (
                "uses k3/group16 v7 rule, but workload extent exceeds direct RTL-clean holdout range"
            )
        return "C_projection_k3_not_directly_run", (
            "uses validated k3/group16 rule but this exact row was not directly RTL-run"
        )
    return "C_projection_requires_more_rtl", "falls outside current A/B evidence boundary"


def build_workload_readiness(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        grade, reason = workload_grade(row)
        out.append(
            {
                "dataset": row.get("dataset"),
                "id": row.get("id"),
                "operator": row.get("operator"),
                "workmode": row.get("rtl_workmode_class"),
                "k": row.get("group16_v5_k"),
                "cout": row.get("group16_v5_cout"),
                "cin_idx_total": row.get("group16_v5_cin_idx_total"),
                "spatial_points": row.get("group16_v5_spatial_points"),
                "pytorchsim_cycles": row.get("pytorchsim_cycles"),
                "group16_v7_cycles": row.get("group16_v7_total_cycles") or row.get("group16_v5_total_cycles"),
                "readiness_grade": grade,
                "readiness_reason": reason,
            }
        )
    return out


def evidence_rows(
    multicin_summary: list[dict[str, str]],
    multicin_holdout_summary: list[dict[str, str]],
    spatial_summary: list[dict[str, str]],
    k3_summary: list[dict[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if multicin_summary:
        row = multicin_summary[0]
        out.append(
            {
                "evidence": "group16_multicin_v5_fit",
                "grade": "A_RTL_clean_fit",
                "cases": row.get("valid_cases"),
                "mean_abs_error_percent": row.get("v5_mean_abs_error_percent"),
                "max_abs_error_percent": row.get("v5_max_abs_error_percent"),
                "scope": "k=1, group_size=16, res=1, multi-Cin",
            }
        )
    if multicin_holdout_summary:
        row = multicin_holdout_summary[0]
        out.append(
            {
                "evidence": "group16_multicin_v5_holdout",
                "grade": "A_RTL_clean_holdout",
                "cases": row.get("valid_cases"),
                "mean_abs_error_percent": row.get("v5_mean_abs_error_percent"),
                "max_abs_error_percent": row.get("v5_max_abs_error_percent"),
                "scope": "k=1, group_size=16, res=1, multi-Cin independent cout/cin",
            }
        )
    for row in spatial_summary:
        split = row["split"]
        if split == "fit":
            grade = "A_RTL_clean_fit"
        elif split == "holdout":
            grade = "A_RTL_clean_holdout"
        else:
            grade = "D_blocked_boundary"
        out.append(
            {
                "evidence": f"group16_spatial_v6_{split}",
                "grade": grade,
                "cases": row.get("paper_candidate_clean_cases") if split != "blocked" else row.get("blocked_cases"),
                "mean_abs_error_percent": row.get("v6_mean_abs_error_percent"),
                "max_abs_error_percent": row.get("v6_max_abs_error_percent"),
                "scope": "k=1, group_size=16, cin=1, res_cols<=2" if split != "blocked" else "res_cols>=3 blocked by Cluster X",
            }
        )
    for row in k3_summary:
        split = row["split"]
        out.append(
            {
                "evidence": f"group16_k3_v7_{split}",
                "grade": "A_RTL_clean_fit" if split == "fit" else "A_RTL_clean_holdout",
                "cases": row.get("rtl_clean_cases"),
                "mean_abs_error_percent": row.get("v7_mean_abs_error_percent"),
                "max_abs_error_percent": row.get("v7_max_abs_error_percent"),
                "scope": "k=3, group_size=16, res=1, cin up to holdout 3",
            }
        )
    return out


def summarize_workload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row["readiness_grade"]), []).append(row)
    out: list[dict[str, Any]] = []
    for grade, items in sorted(groups.items()):
        out.append(
            {
                "readiness_grade": grade,
                "rows": len(items),
                "pytorchsim_cycles": round(sum(fnum(row["pytorchsim_cycles"]) for row in items), 4),
                "group16_v7_cycles": round(sum(fnum(row["group16_v7_cycles"]) for row in items), 4),
            }
        )
    return out


def write_readme(path: Path, evidence: list[dict[str, Any]], workload_summary: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD Paper Data Readiness v1\n\n")
        fh.write("## 结论\n\n")
        fh.write(
            "当前已经具备一批可作为论文材料的 RTL-clean 校准/holdout 证据，"
            "但还不具备完整 workload RTL validation。论文主表应把证据等级分开呈现。\n\n"
        )
        fh.write("## 证据等级定义\n\n")
        fh.write("- `A_RTL_clean_fit`：直接 RTL 样本，无 X/无 0 周期，用于拟合规则。\n")
        fh.write("- `A_RTL_clean_holdout`：未参与拟合的直接 RTL 样本，无 X/无 0 周期，用于独立验证。\n")
        fh.write("- `B_direct_rtl_clean_workload_row`：该 workload 行已经直接 RTL-clean，并且与 projection 一致。\n")
        fh.write("- `C_projection_*`：有局部 RTL 公式支撑，但该 workload 行没有直接跑通，或空间规模超过已验证边界。\n")
        fh.write("- `D_direct_rtl_blocked`：该 workload 行直接 RTL 尝试已经观察到 X/0-cycle 阻塞。\n")
        fh.write("- `D_excluded/D_blocked_boundary/D_observed_*`：不支持或已知 RTL 阻塞边界，不能进论文主性能表。\n\n")
        fh.write("## RTL 证据汇总\n\n")
        fh.write("| evidence | grade | cases | mean abs err % | max abs err % | scope |\n")
        fh.write("|---|---|---:|---:|---:|---|\n")
        for row in evidence:
            fh.write(
                f"| {row['evidence']} | {row['grade']} | {row['cases']} | "
                f"{row['mean_abs_error_percent']} | {row['max_abs_error_percent']} | {row['scope']} |\n"
            )
        fh.write("\n## workload readiness 汇总\n\n")
        fh.write("| grade | rows | PyTorchSim cycles | group16 v7 cycles |\n")
        fh.write("|---|---:|---:|---:|\n")
        for row in workload_summary:
            fh.write(
                f"| {row['readiness_grade']} | {row['rows']} | {row['pytorchsim_cycles']} | {row['group16_v7_cycles']} |\n"
            )
        fh.write("\n## 论文使用建议\n\n")
        fh.write(
            "论文主数据应优先使用 A 级 RTL-clean fit/holdout 表支撑校准公式；"
            "B 级 workload 行可作为 direct RTL-clean workload 子集；"
            "C 级只能作为 RTL-calibrated projection；"
            "D 级 blocked/excluded 不进入主性能表。\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", required=True)
    parser.add_argument("--multicin-summary", required=True)
    parser.add_argument("--multicin-holdout-summary", required=True)
    parser.add_argument("--spatial-summary", required=True)
    parser.add_argument("--k3-summary", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    workload = build_workload_readiness(read_csv(args.workload))
    evidence = evidence_rows(
        read_csv(args.multicin_summary),
        read_csv(args.multicin_holdout_summary),
        read_csv(args.spatial_summary),
        read_csv(args.k3_summary),
    )
    workload_summary = summarize_workload(workload)

    out_dir = Path(args.out_dir)
    write_csv(out_dir / "paper_evidence_summary.csv", evidence)
    write_csv(out_dir / "paper_workload_readiness_details.csv", workload)
    write_csv(out_dir / "paper_workload_readiness_summary.csv", workload_summary)
    write_readme(out_dir / "README.md", evidence, workload_summary)
    print(f"wrote paper data readiness package to {out_dir}")


if __name__ == "__main__":
    main()
