#!/usr/bin/env python3
"""Build a candidate v4 FLOOD RTL calibration from boundary RTL cases."""
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


def v3_final(row: dict[str, str]) -> float:
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


def v4_final(row: dict[str, str]) -> float:
    k = fint(row["k"])
    cout = fint(row["cout"])
    group_size = fint(row["group_size"])
    if k == 1 and group_size == 16:
        return 56.0 + 19.0 * max(0, cout - 2)

    k_extra = max(0, k - 1)
    cout_extra = max(0, cout - 1)
    group_extra = max(0, group_size - 4)
    return v3_final(row) + 2.875 * k_extra * group_extra * cout_extra


def total_from_final(row: dict[str, str], final_cycles: float) -> float:
    cin_idx_total = max(1, fint(row["cin_idx_total"]))
    spatial_points = max(1, fint(row["res_cols"]) * fint(row["res_rows"]))
    per_spatial = (cin_idx_total - 1) * (final_cycles - 3.0) + final_cycles
    return spatial_points * per_spatial


def parse_cycles(value: str) -> list[float]:
    return [fnum(item) for item in value.split(";") if item.strip()]


def is_valid(row: dict[str, str]) -> tuple[bool, str]:
    cycles = parse_cycles(row["cycle_list"])
    expected_runs = max(1, fint(row["cin_idx_total"]) * fint(row["res_cols"]) * fint(row["res_rows"]))
    if fint(row["rc"]) != 0:
        return False, "rtl command returned non-zero"
    if fint(row["run_count"]) != expected_runs:
        return False, f"run_count mismatch: expected {expected_runs}"
    if any(cycle <= 0 for cycle in cycles):
        return False, "zero or negative cycle count observed"
    return True, ""


def load_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["source_file"] = path.name
                rows.append(row)
    return rows


def build_details(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        valid, invalid_reason = is_valid(row)
        measured = fnum(row["total_cycles"])
        v3_total = total_from_final(row, v3_final(row))
        v4_total = total_from_final(row, v4_final(row))
        item: dict[str, Any] = dict(row)
        item["status"] = "valid" if valid else "invalid"
        item["invalid_reason"] = invalid_reason
        item["v3_predicted_total"] = round(v3_total, 4)
        item["v3_error_percent"] = round((v3_total - measured) / measured * 100.0, 4) if measured else 0.0
        item["v4_predicted_total"] = round(v4_total, 4)
        item["v4_error_percent"] = round((v4_total - measured) / measured * 100.0, 4) if measured else 0.0
        out.append(item)
    return out


def summarize(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [row for row in details if row["status"] == "valid"]

    def mae(field: str) -> float:
        return round(sum(abs(fnum(row[field])) for row in valid) / len(valid), 4) if valid else 0.0

    def maxe(field: str) -> float:
        return round(max(abs(fnum(row[field])) for row in valid), 4) if valid else 0.0

    def exact(field: str) -> int:
        return sum(1 for row in valid if abs(fnum(row[field])) < 1e-9)

    return [
        {
            "total_cases": len(details),
            "valid_cases": len(valid),
            "invalid_cases": len(details) - len(valid),
            "v3_exact_cases": exact("v3_error_percent"),
            "v3_mean_abs_error_percent": mae("v3_error_percent"),
            "v3_max_abs_error_percent": maxe("v3_error_percent"),
            "v4_exact_cases": exact("v4_error_percent"),
            "v4_mean_abs_error_percent": mae("v4_error_percent"),
            "v4_max_abs_error_percent": maxe("v4_error_percent"),
            "scope": "candidate calibration fitted with boundary cases",
        }
    ]


def write_readme(path: Path, summary: dict[str, Any], details: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD RTL Boundary Calibration v4\n\n")
        fh.write("## 定位\n\n")
        fh.write(
            "这是一个候选校准版本，用新补的边界 RTL 点修正 v3 公式。"
            "它提高了模型内部一致性，但因为边界点参与了拟合，所以还需要新的独立留出样本验证后才能作为论文性能模型使用。\n\n"
        )
        fh.write("## v4 修正\n\n")
        fh.write("- 对 `k>1` 与 `group_size>4` 增加 `2.875*(k-1)*max(group_size-4,0)*(cout-1)` 交互项。\n")
        fh.write("- 对 `k=1/group_size=16` 使用 `final_run = 56 + 19*max(cout-2,0)`。\n")
        fh.write("- 多 Cin 仍暂按 `nonfinal = final_run - 3`，但 `group_size=16` 多 Cin RTL 已发现控制异常，不能用于论文性能数据。\n\n")
        fh.write("## 汇总\n\n")
        fh.write(f"- 有效样本：{summary['valid_cases']} / {summary['total_cases']}\n")
        fh.write(f"- v3 平均绝对误差：{summary['v3_mean_abs_error_percent']}%，最大：{summary['v3_max_abs_error_percent']}%\n")
        fh.write(f"- v4 平均绝对误差：{summary['v4_mean_abs_error_percent']}%，最大：{summary['v4_max_abs_error_percent']}%\n")
        fh.write(f"- v3 完全命中：{summary['v3_exact_cases']}，v4 完全命中：{summary['v4_exact_cases']}\n\n")
        fh.write("## 下一步验证\n\n")
        fh.write(
            "新增独立样本应避开已用于拟合的点，建议优先跑 "
            "`k=3/group_size=8/cout=6/12`、`k=1/group_size=16/cout=10/16`，"
            "以及修复 testbench 后的 `group_size=16/cin_idx_total>1`。\n\n"
        )
        fh.write("## 明细\n\n")
        fh.write("| case | status | measured | v3 pred | v3 err % | v4 pred | v4 err % |\n")
        fh.write("|---|---|---:|---:|---:|---:|---:|\n")
        for row in details:
            fh.write(
                f"| {row['case']} | {row['status']} | {row['total_cycles']} | "
                f"{row['v3_predicted_total']} | {row['v3_error_percent']} | "
                f"{row['v4_predicted_total']} | {row['v4_error_percent']} |\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    details = build_details(load_rows([Path(item) for item in args.input]))
    summary = summarize(details)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "rtl_boundary_calibration_v4_details.csv", details)
    write_csv(out_dir / "rtl_boundary_calibration_v4_summary.csv", summary)
    write_readme(out_dir / "README.md", summary[0], details)
    print(f"wrote RTL boundary calibration v4 report to {out_dir}")


if __name__ == "__main__":
    main()
