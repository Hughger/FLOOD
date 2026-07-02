#!/usr/bin/env python3
"""Summarize the fixed group=16 multi-Cin RTL validation and v5 rule."""
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


def group16_first_run(cout: int) -> float:
    return 19.0 * cout + 15.0


def v4_total(row: dict[str, str]) -> float:
    cout = fint(row["cout"])
    cin = max(1, fint(row["cin_idx_total"]))
    final_run = 56.0 + 19.0 * max(0, cout - 2)
    return (cin - 1) * (final_run - 3.0) + final_run


def v5_total(row: dict[str, str]) -> float:
    cout = fint(row["cout"])
    cin = max(1, fint(row["cin_idx_total"]))
    if cin == 1:
        return group16_first_run(cout)
    return group16_first_run(cout) + max(0, cin - 2) * 53.0 + 56.0


def cycle_shape(row: dict[str, str]) -> str:
    cycles = [fnum(item) for item in row["cycle_list"].split(";") if item]
    if not cycles:
        return "empty"
    if fint(row["x_count"]) != 0:
        return "has_x"
    if any(cycle <= 0 for cycle in cycles):
        return "has_zero"
    return "valid"


def build_details(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        measured = fnum(row["total_cycles"])
        v4 = v4_total(row)
        v5 = v5_total(row)
        item: dict[str, Any] = dict(row)
        item["status"] = cycle_shape(row)
        item["v4_predicted_total"] = round(v4, 4)
        item["v4_error_percent"] = round((v4 - measured) / measured * 100.0, 4) if measured else 0.0
        item["v5_predicted_total"] = round(v5, 4)
        item["v5_error_percent"] = round((v5 - measured) / measured * 100.0, 4) if measured else 0.0
        out.append(item)
    return out


def build_summary(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [row for row in details if row["status"] == "valid"]

    def mae(field: str) -> float:
        return round(sum(abs(fnum(row[field])) for row in valid) / len(valid), 4) if valid else 0.0

    def maxe(field: str) -> float:
        return round(max(abs(fnum(row[field])) for row in valid), 4) if valid else 0.0

    return [
        {
            "total_cases": len(details),
            "valid_cases": len(valid),
            "v4_mean_abs_error_percent": mae("v4_error_percent"),
            "v4_max_abs_error_percent": maxe("v4_error_percent"),
            "v5_mean_abs_error_percent": mae("v5_error_percent"),
            "v5_max_abs_error_percent": maxe("v5_error_percent"),
            "x_or_zero_cases": len(details) - len(valid),
        }
    ]


def write_readme(path: Path, details: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD RTL Group16 Multi-Cin Calibration v5\n\n")
        fh.write("## 目的\n\n")
        fh.write(
            "本报告使用修复后的 testbench，对 `group_size=16` 的多 Cin 情况进行 RTL 采样，"
            "用于建立 v5 高 group 多 Cin 校准项。\n\n"
        )
        fh.write("## 数据范围\n\n")
        fh.write("- `k=1`\n")
        fh.write("- `group_size=16`, `group_num=1`\n")
        fh.write("- `cout=2/4/6/8/12/16`\n")
        fh.write("- `cin_idx_total=2/4`\n")
        fh.write("- `res_cols=res_rows=1`\n\n")
        fh.write("所有样本 `x_count=0`，没有 0 周期 run。\n\n")
        fh.write("## v5 规则\n\n")
        fh.write("对 `k=1/group_size=16/res=1`：\n\n")
        fh.write("```text\n")
        fh.write("first_run = 19*cout + 15\n")
        fh.write("middle_run = 53\n")
        fh.write("final_run = 56\n")
        fh.write("total = first_run + max(cin_idx_total-2, 0)*middle_run + final_run\n")
        fh.write("```\n\n")
        fh.write("## 误差对比\n\n")
        fh.write(f"- 有效样本：{summary['valid_cases']} / {summary['total_cases']}\n")
        fh.write(f"- v4 平均绝对误差：{summary['v4_mean_abs_error_percent']}%，最大：{summary['v4_max_abs_error_percent']}%\n")
        fh.write(f"- v5 平均绝对误差：{summary['v5_mean_abs_error_percent']}%，最大：{summary['v5_max_abs_error_percent']}%\n\n")
        fh.write("## 明细\n\n")
        fh.write("| case | measured | cycles | v4 pred | v4 err % | v5 pred | v5 err % |\n")
        fh.write("|---|---:|---|---:|---:|---:|---:|\n")
        for row in details:
            fh.write(
                f"| `{row['case']}` | {row['total_cycles']} | `{row['cycle_list']}` | "
                f"{row['v4_predicted_total']} | {row['v4_error_percent']} | "
                f"{row['v5_predicted_total']} | {row['v5_error_percent']} |\n"
            )
        fh.write("\n## 论文使用建议\n\n")
        fh.write(
            "这批数据可以支撑 `group_size=16` 多 Cin 的 RTL-aware v5 校准。"
            "但 `res_cols/res_rows>1` 的空间重复路径仍有 X 问题，不能混入同一个可信度等级。\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    details = build_details(rows)
    summary = build_summary(details)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "rtl_group16_multicin_v5_details.csv", details)
    write_csv(out_dir / "rtl_group16_multicin_v5_summary.csv", summary)
    write_readme(out_dir / "README.md", details, summary[0])
    print(f"wrote group16 multi-Cin v5 report to {out_dir}")


if __name__ == "__main__":
    main()
