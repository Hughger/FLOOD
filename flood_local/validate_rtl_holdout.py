#!/usr/bin/env python3
"""Validate the FLOOD RTL-aware cycle formula on holdout RTL cases.

These cases are intentionally kept separate from the bring-up calibration set.
The report is meant to show where the current model generalizes and where it
still needs more RTL evidence before being used as paper-grade data.
"""
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
    return int(fnum(value))


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


def predict_final_run_cycles(row: dict[str, str]) -> float:
    """Current v3 formula fitted only from the RTL bring-up matrix."""
    k = fint(row["k"])
    cout = fint(row["cout"])
    group_size = fint(row["group_size"])
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


def predict_cycle_list(row: dict[str, str]) -> list[float]:
    cin_idx_total = max(1, fint(row["cin_idx_total"]))
    spatial_points = max(1, fint(row["res_cols"]) * fint(row["res_rows"]))
    final_cycles = predict_final_run_cycles(row)
    cycles: list[float] = []
    for _ in range(spatial_points):
        cycles.extend(final_cycles - 3.0 for _ in range(cin_idx_total - 1))
        cycles.append(final_cycles)
    return cycles


def parse_cycle_list(value: str) -> list[float]:
    return [fnum(item) for item in value.split(";") if item.strip()]


def classify_row(row: dict[str, str]) -> tuple[str, str]:
    cycles = parse_cycle_list(row["cycle_list"])
    expected_runs = max(1, fint(row["cin_idx_total"]) * fint(row["res_cols"]) * fint(row["res_rows"]))
    if fint(row["rc"]) != 0:
        return "invalid", "rtl command returned non-zero"
    if fint(row["run_count"]) != expected_runs:
        return "invalid", f"run_count mismatch: expected {expected_runs}"
    if any(cycle <= 0 for cycle in cycles):
        return "invalid", "zero or negative cycle count observed"
    return "valid", ""


def load_rows(inputs: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in inputs:
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["source_file"] = path.name
                rows.append(row)
    return rows


def build_details(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for row in rows:
        status, invalid_reason = classify_row(row)
        predicted_cycles = predict_cycle_list(row)
        predicted_total = sum(predicted_cycles)
        measured = fnum(row["total_cycles"])
        error_cycles = predicted_total - measured
        error_percent = error_cycles / measured * 100.0 if measured else 0.0

        item: dict[str, Any] = dict(row)
        item["status"] = status
        item["invalid_reason"] = invalid_reason
        item["predicted_cycle_list"] = ";".join(str(round(cycle, 4)) for cycle in predicted_cycles)
        item["predicted_total_cycles"] = round(predicted_total, 4)
        item["error_cycles"] = round(error_cycles, 4)
        item["error_percent"] = round(error_percent, 4)
        item["abs_error_percent"] = round(abs(error_percent), 4)
        details.append(item)
    return details


def build_summary(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [row for row in details if row["status"] == "valid"]
    invalid = [row for row in details if row["status"] != "valid"]
    exact = [row for row in valid if abs(fnum(row["error_cycles"])) < 1e-9]
    abs_pct = [fnum(row["abs_error_percent"]) for row in valid]
    abs_cycles = [abs(fnum(row["error_cycles"])) for row in valid]
    return [
        {
            "total_cases": len(details),
            "valid_cases": len(valid),
            "invalid_cases": len(invalid),
            "exact_match_cases": len(exact),
            "mean_abs_error_percent_valid": round(sum(abs_pct) / len(abs_pct), 4) if abs_pct else 0.0,
            "max_abs_error_percent_valid": round(max(abs_pct), 4) if abs_pct else 0.0,
            "mean_abs_error_cycles_valid": round(sum(abs_cycles) / len(abs_cycles), 4) if abs_cycles else 0.0,
            "max_abs_error_cycles_valid": round(max(abs_cycles), 4) if abs_cycles else 0.0,
            "paper_use": "diagnostic holdout evidence; not final paper-grade performance data",
        }
    ]


def write_readme(path: Path, details: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    valid = [row for row in details if row["status"] == "valid"]
    invalid = [row for row in details if row["status"] != "valid"]
    exact = [row for row in valid if abs(fnum(row["error_cycles"])) < 1e-9]
    misses = [row for row in valid if abs(fnum(row["error_cycles"])) >= 1e-9]

    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD RTL 留出验证报告 v1\n\n")
        fh.write("## 目的\n\n")
        fh.write(
            "这份报告只使用没有参与公式拟合的 RTL 小样本，用来检查当前 "
            "RTL-aware 公式是否真的能外推。它的价值不是证明模型已经完成，"
            "而是把可信和不可信的边界说清楚。\n\n"
        )
        fh.write("## 当前公式\n\n")
        fh.write(
            "`final_run = 35 + 13*(cout-1) + 22*(k-1) + "
            "20.5*(k-1)*(cout-1) + 1.5*max(group_size-4,0) + "
            "0.375*max(group_size-8,0) + 2.75*(k-1)*max(group_size-4,0)`\n\n"
        )
        fh.write("多 Cin 情况下，非最后一次 run 暂按 `final_run - 3` 估计。\n\n")
        fh.write("## 总体结果\n\n")
        fh.write(f"- 总样本数：{summary['total_cases']}\n")
        fh.write(f"- 有效样本数：{summary['valid_cases']}\n")
        fh.write(f"- 异常/无效样本数：{summary['invalid_cases']}\n")
        fh.write(f"- 完全命中样本数：{summary['exact_match_cases']}\n")
        fh.write(f"- 有效样本平均绝对误差：{summary['mean_abs_error_percent_valid']}%\n")
        fh.write(f"- 有效样本最大绝对误差：{summary['max_abs_error_percent_valid']}%\n\n")
        fh.write("## 结论\n\n")
        fh.write(
            "- 当前公式在 `group_size=4`、`k=1/group_size=8`、多 Cin、多空间点以及部分较大 `cout` 组合上可以完全命中 RTL。\n"
        )
        fh.write(
            "- `h02_k3_c4_g8_ci2` 暴露了 `k>1` 与 `group_size=8` 的交互项不足，说明卷积核尺寸和 group 并行度不能继续简单相加。\n"
        )
        fh.write(
            "- 当前公式在 `group_size=16` 且 `cout` 增大时开始低估周期，说明高 group 边界还需要补充 RTL 样本和公式项。\n"
        )
        fh.write(
            "- `h04_k1_c6_g16_ci4` 出现后续 run 为 0 的现象，暂判为 testbench/中断清除边界问题，不能作为性能数据使用。\n\n"
        )
        fh.write("## 有效样本明细\n\n")
        fh.write("| case | measured | predicted | error cycles | error % | note |\n")
        fh.write("|---|---:|---:|---:|---:|---|\n")
        for row in valid:
            note = "exact" if row in exact else "model gap"
            fh.write(
                f"| {row['case']} | {row['total_cycles']} | {row['predicted_total_cycles']} | "
                f"{row['error_cycles']} | {row['error_percent']} | {note} |\n"
            )
        if invalid:
            fh.write("\n## 异常样本\n\n")
            fh.write("| case | measured cycle_list | reason |\n")
            fh.write("|---|---|---|\n")
            for row in invalid:
                fh.write(f"| {row['case']} | `{row['cycle_list']}` | {row['invalid_reason']} |\n")
        fh.write("\n## 下一步\n\n")
        fh.write(
            "为了把数据推进到论文级，下一批 RTL 应重点覆盖 `group_size=16` 下 "
            "`cout=2/4/6/8/12/16`、`cin_idx_total=1/2/4`，同时补齐 "
            "`k=3/group_size=8` 的交互样本，并修复多 Cin 的 done/interrupt 清除问题。\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    inputs = [Path(item) for item in args.input]
    details = build_details(load_rows(inputs))
    summary = build_summary(details)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "rtl_holdout_details.csv", details)
    write_csv(out_dir / "rtl_holdout_summary.csv", summary)
    write_readme(out_dir / "README.md", details, summary[0])
    print(f"wrote RTL holdout report to {out_dir}")


if __name__ == "__main__":
    main()
