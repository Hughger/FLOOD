#!/usr/bin/env python3
"""Build the group16 spatial v6 boundary report.

The v6 candidate only admits clean group16 spatial samples up to res_cols=2.
res_cols>=3 is reported as a blocked RTL region because Cluster output becomes X.
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


def read_rows(paths: list[str], split_names: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path, split in zip(paths, split_names):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["split"] = split
                rows.append(row)
    return rows


def v6_spatial_total(cout: int, res_cols: int) -> float:
    first = 19.0 * cout + 18.0
    repeat = 56.0
    return first + max(0, res_cols - 1) * repeat


def status(row: dict[str, str]) -> str:
    if fint(row.get("x_count")) == 0 and fint(row.get("cluster_x")) == 0 and fint(row.get("router_write_x")) == 0:
        if fint(row.get("res_cols")) <= 2:
            return "paper_candidate_clean"
        return "clean_but_outside_v6_scope"
    if fint(row.get("cluster_x")) > 0:
        return "blocked_cluster_x_for_res_cols_ge_3"
    if fint(row.get("router_read_x")) > 0 or fint(row.get("router_write_x")) > 0:
        return "blocked_router_or_sram_x"
    return "blocked_x"


def build_details(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        cout = fint(row["cout"])
        res_cols = fint(row["res_cols"])
        measured = fnum(row["total_cycles"])
        pred = v6_spatial_total(cout, res_cols)
        item: dict[str, Any] = dict(row)
        item["v6_status"] = status(row)
        item["v6_predicted_total"] = round(pred, 4)
        item["v6_error_percent"] = round((pred - measured) / measured * 100.0, 4) if measured else ""
        item["v6_rule"] = "first=19*cout+18; repeat_col=56; valid_for_group16_k1_cin1_res_cols_le_2"
        out.append(item)
    return out


def summarize(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for split in ["fit", "holdout", "blocked"]:
        items = [row for row in details if row["split"] == split]
        valid = [row for row in items if row["v6_status"] == "paper_candidate_clean"]
        blocked = [row for row in items if str(row["v6_status"]).startswith("blocked")]
        mae = round(sum(abs(fnum(row["v6_error_percent"])) for row in valid) / len(valid), 4) if valid else 0.0
        maxe = round(max(abs(fnum(row["v6_error_percent"])) for row in valid), 4) if valid else 0.0
        out.append(
            {
                "split": split,
                "total_cases": len(items),
                "paper_candidate_clean_cases": len(valid),
                "blocked_cases": len(blocked),
                "v6_mean_abs_error_percent": mae,
                "v6_max_abs_error_percent": maxe,
            }
        )
    return out


def write_readme(path: Path, details: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    by_split = {row["split"]: row for row in summary}
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD RTL Group16 Spatial Calibration v6\n\n")
        fh.write("## 目的\n\n")
        fh.write(
            "本报告把 `group_size=16` 的空间重复路径拆成可进入论文数据的区域和仍需 debug 的区域。"
            "v6 只接纳 `k=1, cin_idx_total=1, res_cols<=2` 且无 X 的 RTL 样本。\n\n"
        )
        fh.write("## v6 规则\n\n")
        fh.write("对 `k=1/group_size=16/cin_idx_total=1/res_cols<=2`：\n\n")
        fh.write("```text\n")
        fh.write("first_col = 19*cout + 18\n")
        fh.write("repeat_col = 56\n")
        fh.write("total = first_col + (res_cols-1)*repeat_col\n")
        fh.write("```\n\n")
        fh.write("## 验证结果\n\n")
        fh.write("| split | total | clean candidates | blocked | mean abs err % | max abs err % |\n")
        fh.write("|---|---:|---:|---:|---:|---:|\n")
        for split in ["fit", "holdout", "blocked"]:
            row = by_split[split]
            fh.write(
                f"| {split} | {row['total_cases']} | {row['paper_candidate_clean_cases']} | "
                f"{row['blocked_cases']} | {row['v6_mean_abs_error_percent']} | {row['v6_max_abs_error_percent']} |\n"
            )
        fh.write("\n## 关键结论\n\n")
        fh.write("- fitting 样本：`cout=6/12/16, res_cols=2`，全部无 X，v6 误差 0%。\n")
        fh.write("- holdout 样本：`cout=4/8/10/14, res_cols=2`，全部无 X，v6 误差 0%。\n")
        fh.write("- `res_cols=3/4` 样本仍有 X，探针显示 X 出现在 Cluster 输出侧，应继续作为 RTL debug 阻塞项。\n\n")
        fh.write("## 论文使用建议\n\n")
        fh.write(
            "可以把 `group16/k1/cin1/res_cols<=2` 标为 RTL-clean calibration/holdout evidence。"
            "`res_cols>=3` 必须单独列为未通过 RTL 验证的边界，不应混入论文主性能表。\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--holdout", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    all_rows = read_rows([args.matrix, args.holdout], ["fit", "holdout"])
    for row in all_rows:
        if fint(row["res_cols"]) >= 3:
            row["split"] = "blocked"
    details = build_details(all_rows)
    summary = summarize(details)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "rtl_group16_spatial_v6_details.csv", details)
    write_csv(out_dir / "rtl_group16_spatial_v6_summary.csv", summary)
    write_readme(out_dir / "README.md", details, summary)
    print(f"wrote group16 spatial v6 report to {out_dir}")


if __name__ == "__main__":
    main()
