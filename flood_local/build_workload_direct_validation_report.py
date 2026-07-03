#!/usr/bin/env python3
"""Build the first direct workload RTL validation report."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


def fnum(value: Any) -> float:
    if value in ("", None, "NA"):
        return 0.0
    return float(value)


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


def build_projection_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["id"]: row for row in rows}


def build_details(
    direct_rows: list[dict[str, str]],
    blocked_rows: list[dict[str, str]],
    projection_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    projection = build_projection_index(projection_rows)
    out: list[dict[str, Any]] = []
    for row in direct_rows:
        wid = row["workload_id"]
        pred = fnum(projection.get(wid, {}).get("group16_v7_total_cycles"))
        measured = fnum(row["total_cycles"])
        out.append(
            {
                "case": row["case"],
                "dataset": row["dataset"],
                "workload_id": wid,
                "operator": projection.get(wid, {}).get("operator", ""),
                "workmode": projection.get(wid, {}).get("rtl_workmode_class", ""),
                "k": row["k"],
                "cout": row["cout"],
                "cin_idx_total": row["cin_idx_total"],
                "spatial_points": row["spatial_points"],
                "direct_status": "rtl_clean_direct",
                "direct_total_cycles": measured,
                "projected_group16_v7_cycles": pred,
                "error_percent": round((pred - measured) / measured * 100.0, 4) if measured else "",
                "x_count": row["x_count"],
                "zero_cycles": 0,
                "cycle_list": row["cycle_list"],
                "blocked_reason": "",
            }
        )
    for row in blocked_rows:
        wid = row["workload_id"]
        out.append(
            {
                "case": row["case"],
                "dataset": row["dataset"],
                "workload_id": wid,
                "operator": projection.get(wid, {}).get("operator", ""),
                "workmode": projection.get(wid, {}).get("rtl_workmode_class", ""),
                "k": row["k"],
                "cout": row["cout"],
                "cin_idx_total": row["cin_idx_total"],
                "spatial_points": row["spatial_points"],
                "direct_status": row["status"],
                "direct_total_cycles": "",
                "projected_group16_v7_cycles": row["expected_v7_total_cycles"],
                "error_percent": "",
                "x_count": row["observed_x_count"],
                "zero_cycles": row["observed_zero_cycles"],
                "cycle_list": row["observed_cycle_prefix"],
                "blocked_reason": row["note"],
            }
        )
    return out


def summarize(details: list[dict[str, Any]], workload_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    clean = [row for row in details if row["direct_status"] == "rtl_clean_direct"]
    blocked = [row for row in details if "blocked" in str(row["direct_status"])]
    total_candidates = [row for row in workload_rows if row.get("operator") in {"conv", "gemm"}]
    clean_error = [abs(fnum(row["error_percent"])) for row in clean if row["error_percent"] != ""]
    return [
        {
            "direct_attempted_cases": len(details),
            "direct_clean_cases": len(clean),
            "direct_blocked_cases": len(blocked),
            "workload_candidate_rows_total": len(total_candidates),
            "direct_clean_row_coverage_percent": round(len(clean) / len(total_candidates) * 100.0, 4) if total_candidates else 0.0,
            "direct_clean_mean_abs_error_percent": round(sum(clean_error) / len(clean_error), 4) if clean_error else 0.0,
            "direct_clean_max_abs_error_percent": round(max(clean_error), 4) if clean_error else 0.0,
            "blocked_reason_summary": "blocked cases have Cluster/Router/Output X or repeated 0-cycle behavior and are excluded from clean evidence",
        }
    ]


def write_readme(path: Path, details: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD Workload Direct RTL Validation v1\n\n")
        fh.write("## 目的\n\n")
        fh.write(
            "本报告开始把 workload 行从 `RTL-calibrated projection` 推进到直接 RTL validation。"
            "第一批选择 Icarus 可承受的小型 synthetic workload 行，并尝试一个真实 workload GEMM 行。\n\n"
        )
        fh.write("## 总结\n\n")
        fh.write(f"- direct attempted cases: {summary['direct_attempted_cases']}\n")
        fh.write(f"- direct clean cases: {summary['direct_clean_cases']}\n")
        fh.write(f"- direct blocked cases: {summary['direct_blocked_cases']}\n")
        fh.write(f"- clean row coverage among conv/gemm workload candidates: {summary['direct_clean_row_coverage_percent']}%\n")
        fh.write(f"- clean direct-vs-projection mean abs error: {summary['direct_clean_mean_abs_error_percent']}%\n")
        fh.write(f"- clean direct-vs-projection max abs error: {summary['direct_clean_max_abs_error_percent']}%\n\n")
        fh.write("## 明细\n\n")
        fh.write("| case | dataset | workload id | status | direct cycles | projected cycles | err % | x_count | zero cycles |\n")
        fh.write("|---|---|---|---|---:|---:|---:|---:|---:|\n")
        for row in details:
            fh.write(
                f"| `{row['case']}` | {row['dataset']} | `{row['workload_id']}` | {row['direct_status']} | "
                f"{row['direct_total_cycles']} | {row['projected_group16_v7_cycles']} | {row['error_percent']} | "
                f"{row['x_count']} | {row['zero_cycles']} |\n"
            )
        fh.write("\n## 阻塞结论\n\n")
        fh.write(
            "直接 RTL 尝试已经观察到两类阻塞：`attn_score_1024_64_1024` 在大空间循环下出现 "
            "`Cluster_OUT` X、Router X 和大量 0-cycle run；`trace_conv_018` 的周期数匹配投影，"
            "但 XPROBE2 显示 Cluster/Router/Output 侧存在 X 污染。"
            "这些样本不能作为 clean direct RTL 样本；完整 workload RTL validation 的下一步应定位状态清零、"
            "输出 SRAM/Router 写读有效性和长空间循环下的 Cluster 状态污染。\n\n"
        )
        fh.write("## 论文使用建议\n\n")
        fh.write(
            "这批数据可作为“direct RTL validation 已开始覆盖 workload 子集”的证据。"
            "clean synthetic workload 行可进入支撑证据；blocked 行必须单独列为 RTL debug 边界，不进入主性能表。\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct-subset", required=True)
    parser.add_argument("--blocked", required=True)
    parser.add_argument("--workload-projection", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    details = build_details(read_csv(args.direct_subset), read_csv(args.blocked), read_csv(args.workload_projection))
    summary_rows = summarize(details, read_csv(args.workload_projection))
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "workload_direct_validation_details.csv", details)
    write_csv(out_dir / "workload_direct_validation_summary.csv", summary_rows)
    write_readme(out_dir / "README.md", details, summary_rows[0])
    print(f"wrote workload direct validation report to {out_dir}")


if __name__ == "__main__":
    main()
