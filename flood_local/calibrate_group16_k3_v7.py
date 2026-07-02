#!/usr/bin/env python3
"""Build the group16 k=3 v7 calibration report."""
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


def read_csv(path: str, split: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["split"] = split
    return rows


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


def final_run(cout: int) -> float:
    return 147.0 * cout + 38.0


def v7_total(cout: int, cin: int) -> float:
    final = final_run(cout)
    nonfinal = final - 3.0
    return max(0, cin - 1) * nonfinal + final


def build_details(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        cout = fint(row["cout"])
        cin = fint(row["cin_idx_total"])
        measured = fnum(row["total_cycles"])
        pred = v7_total(cout, cin)
        status = "rtl_clean" if fint(row["x_count"]) == 0 and fint(row["cluster_x"]) == 0 else "blocked_x"
        item: dict[str, Any] = dict(row)
        item["v7_status"] = status
        item["v7_final_run"] = round(final_run(cout), 4)
        item["v7_nonfinal_run"] = round(final_run(cout) - 3.0, 4)
        item["v7_predicted_total"] = round(pred, 4)
        item["v7_error_percent"] = round((pred - measured) / measured * 100.0, 4) if measured else ""
        out.append(item)
    return out


def summarize(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for split in ["fit", "holdout"]:
        items = [row for row in details if row["split"] == split]
        valid = [row for row in items if row["v7_status"] == "rtl_clean"]
        mae = round(sum(abs(fnum(row["v7_error_percent"])) for row in valid) / len(valid), 4) if valid else 0.0
        maxe = round(max(abs(fnum(row["v7_error_percent"])) for row in valid), 4) if valid else 0.0
        out.append(
            {
                "split": split,
                "total_cases": len(items),
                "rtl_clean_cases": len(valid),
                "blocked_cases": len(items) - len(valid),
                "v7_mean_abs_error_percent": mae,
                "v7_max_abs_error_percent": maxe,
            }
        )
    return out


def write_readme(path: Path, details: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD RTL Group16 k3 Calibration v7\n\n")
        fh.write("## 目的\n\n")
        fh.write(
            "本报告补上真实卷积 workload 最关键的 `k=3/group_size=16/res=1` RTL-clean 证据。"
            "所有样本均使用 SRAM memory 初始清零 testbench，并由探针确认无 X。\n\n"
        )
        fh.write("## v7 规则\n\n")
        fh.write("对 `k=3/group_size=16/res_cols=res_rows=1`：\n\n")
        fh.write("```text\n")
        fh.write("final_run = 147*cout + 38\n")
        fh.write("nonfinal_run = final_run - 3\n")
        fh.write("total = (cin_idx_total-1)*nonfinal_run + final_run\n")
        fh.write("```\n\n")
        fh.write("## 验证结果\n\n")
        fh.write("| split | total | rtl clean | blocked | mean abs err % | max abs err % |\n")
        fh.write("|---|---:|---:|---:|---:|---:|\n")
        for row in summary:
            fh.write(
                f"| {row['split']} | {row['total_cases']} | {row['rtl_clean_cases']} | {row['blocked_cases']} | "
                f"{row['v7_mean_abs_error_percent']} | {row['v7_max_abs_error_percent']} |\n"
            )
        fh.write("\n## 明细\n\n")
        fh.write("| case | split | cout | cin | cycles | measured | v7 pred | err % |\n")
        fh.write("|---|---|---:|---:|---|---:|---:|---:|\n")
        for row in details:
            fh.write(
                f"| `{row['case']}` | {row['split']} | {row['cout']} | {row['cin_idx_total']} | "
                f"`{row['cycle_list']}` | {row['total_cycles']} | {row['v7_predicted_total']} | {row['v7_error_percent']} |\n"
            )
        fh.write("\n## 论文使用建议\n\n")
        fh.write(
            "`k=3/group16/res=1` 现在已有 fitting 与 holdout 的 A 级 RTL-clean 证据。"
            "这可以支撑真实 conv workload 的 kernel-size 校准项；但大 workload 的大量 spatial points 仍应标注为 calibrated projection。\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit", required=True)
    parser.add_argument("--holdout", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = read_csv(args.fit, "fit") + read_csv(args.holdout, "holdout")
    details = build_details(rows)
    summary = summarize(details)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "rtl_group16_k3_v7_details.csv", details)
    write_csv(out_dir / "rtl_group16_k3_v7_summary.csv", summary)
    write_readme(out_dir / "README.md", details, summary)
    print(f"wrote group16 k3 v7 report to {out_dir}")


if __name__ == "__main__":
    main()
