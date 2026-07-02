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


def workload_grade(row: dict[str, str]) -> tuple[str, str]:
    op = row.get("operator", "")
    if op not in {"conv", "gemm"}:
        return "D_excluded", "operator_not_supported_by_current_flood_rtl_model"

    k = fint(row.get("group16_v5_k"))
    cin = fint(row.get("group16_v5_cin_idx_total"))
    workmode = row.get("rtl_workmode_class", "")

    if k == 1 and workmode in {"gemm", "pointwise_conv"} and cin >= 1:
        return "B_projection_from_validated_k1_group16_rules", (
            "uses v5 multi-Cin rule; workload-level spatial/m-block repetition remains calibrated projection"
        )
    if k == 3:
        return "B_projection_from_validated_k3_group16_rules", (
            "uses v7 k3/group16 rule; large workload spatial/multi-Cin extent remains calibrated projection"
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
        fh.write("- `B_projection_from_validated_k1_group16_rules`：workload 行使用已验证 k1/group16 规则外推。\n")
        fh.write("- `B_projection_from_validated_k3_group16_rules`：workload 行使用已验证 k3/group16 规则外推。\n")
        fh.write("- `C_projection_outside_current_group16_rtl_clean_scope`：workload 行超出当前 clean RTL 边界，只能作为 calibrated projection。\n")
        fh.write("- `D_excluded/D_blocked_boundary`：不支持或已知 RTL 阻塞边界，不能进论文主性能表。\n\n")
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
            "B/C 级 workload 结果可以作为 RTL-calibrated projection，并在图注中明确不是 full workload RTL。"
            "`res_cols>=3` 和 softmax 暂不进入主性能表。\n"
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
