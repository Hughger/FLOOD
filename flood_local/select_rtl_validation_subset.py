#!/usr/bin/env python3
"""Select representative workload rows for direct RTL validation."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


DEFAULT_EXCLUDED_STATUSES = {
    "D_direct_rtl_blocked",
    "D_excluded",
    "D_observed_high_cout_multicin_boundary",
}


def fnum(value: Any) -> float:
    if value in ("", None, "NA"):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def fint(value: Any) -> int:
    return int(round(fnum(value)))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
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


def candidate_reason(row: dict[str, str], max_primary_spatial: int, max_primary_cin: int) -> tuple[int, str, str]:
    status = row.get("group16_v7_adversarial_scope_status", "")
    op = row.get("operator", "")
    workmode = row.get("rtl_workmode_class", "")
    py_cycles = fnum(row.get("pytorchsim_cycles"))
    spatial = fint(row.get("group16_v7_spatial_points") or row.get("group16_v5_spatial_points"))
    cin = fint(row.get("group16_v7_cin_idx_total") or row.get("group16_v5_cin_idx_total"))
    cout = fint(row.get("group16_v7_cout") or row.get("group16_v5_cout"))
    k = fint(row.get("group16_v7_k") or row.get("group16_v5_k"))
    feasibility = "primary"
    if spatial > max_primary_spatial or cin > max_primary_cin:
        feasibility = "heavy_diagnostic"

    if status == "B_direct_rtl_clean_workload_row":
        return 10, "already direct-clean; useful only as regression sample", "regression"
    if status.startswith("C_projection_large_k3"):
        if feasibility == "heavy_diagnostic":
            return 300 + int(py_cycles / 10000), "large k3 projection; keep for diagnostic after small RTL pass", feasibility
        return 1000 + int(py_cycles / 1000), "high-priority k3 projection within primary RTL size", feasibility
    if status.startswith("C_projection_large_spatial"):
        if feasibility == "heavy_diagnostic":
            return 280 + int(py_cycles / 10000), "large k1 spatial projection; keep for diagnostic after small RTL pass", feasibility
        return 900 + int(py_cycles / 1000), "high-priority k1 spatial projection within primary RTL size", feasibility
    if status.startswith("C_projection_small"):
        return 700 + int(py_cycles / 1000), "small projection not directly run", feasibility
    if op == "conv" or workmode == "spatial_conv":
        return 400 + spatial + cin + cout + k, "operator/workmode coverage", feasibility
    if op == "gemm" or workmode == "gemm":
        return 350 + spatial + cin + cout, "operator/workmode coverage", feasibility
    return 100, "fallback candidate", feasibility


def select_rows(
    rows: list[dict[str, str]],
    max_rows: int,
    include_b: bool,
    max_primary_spatial: int,
    max_primary_cin: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        status = row.get("group16_v7_adversarial_scope_status", "")
        if status in DEFAULT_EXCLUDED_STATUSES:
            continue
        if status == "B_direct_rtl_clean_workload_row" and not include_b:
            continue
        score, reason, feasibility = candidate_reason(row, max_primary_spatial, max_primary_cin)
        candidates.append(
            {
                "id": row.get("id", ""),
                "dataset": row.get("dataset", ""),
                "operator": row.get("operator", ""),
                "workmode": row.get("rtl_workmode_class", ""),
                "shape_args": row.get("shape_args", ""),
                "pytorchsim_cycles": row.get("pytorchsim_cycles", ""),
                "group16_v7_cycles": row.get("group16_v7_total_cycles", ""),
                "scope_status": status,
                "k": row.get("group16_v7_k") or row.get("group16_v5_k", ""),
                "cout": row.get("group16_v7_cout") or row.get("group16_v5_cout", ""),
                "cin_idx_total": row.get("group16_v7_cin_idx_total") or row.get("group16_v5_cin_idx_total", ""),
                "spatial_points": row.get("group16_v7_spatial_points") or row.get("group16_v5_spatial_points", ""),
                "feasibility": feasibility,
                "selection_score": score,
                "selection_reason": reason,
            }
        )

    candidates.sort(key=lambda row: (-fnum(row["selection_score"]), -fnum(row["pytorchsim_cycles"]), row["id"]))

    selected: list[dict[str, Any]] = []
    seen_buckets: set[tuple[str, str, str]] = set()
    for row in candidates:
        bucket = (row["operator"], row["workmode"], row["scope_status"], row["feasibility"])
        if bucket in seen_buckets and len(selected) < max_rows // 2:
            continue
        selected.append(row)
        seen_buckets.add(bucket)
        if len(selected) >= max_rows:
            break

    if len(selected) < max_rows:
        selected_ids = {row["id"] for row in selected}
        for row in candidates:
            if row["id"] not in selected_ids:
                selected.append(row)
                selected_ids.add(row["id"])
            if len(selected) >= max_rows:
                break
    return selected


def write_readme(path: Path, selected: list[dict[str, Any]], source: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# RTL Validation Candidate Subset\n\n")
        fh.write(f"Source: `{source}`\n\n")
        fh.write("This file lists workload rows recommended for direct RTL validation.\n\n")
        fh.write("Rows with known D-level blocked/excluded status are excluded by default.\n\n")
        fh.write("| id | scope | feasibility | op | workmode | PyTorchSim cycles | reason |\n")
        fh.write("|---|---|---|---|---|---:|---|\n")
        for row in selected:
            fh.write(
                f"| `{row['id']}` | `{row['scope_status']}` | `{row['feasibility']}` | `{row['operator']}` | `{row['workmode']}` | "
                f"{row['pytorchsim_cycles']} | {row['selection_reason']} |\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--readme", required=True)
    parser.add_argument("--max-rows", type=int, default=12)
    parser.add_argument("--include-b", action="store_true")
    parser.add_argument("--max-primary-spatial", type=int, default=64)
    parser.add_argument("--max-primary-cin", type=int, default=36)
    args = parser.parse_args()

    input_path = Path(args.input)
    rows = read_csv(input_path)
    selected = select_rows(
        rows,
        max_rows=args.max_rows,
        include_b=args.include_b,
        max_primary_spatial=args.max_primary_spatial,
        max_primary_cin=args.max_primary_cin,
    )
    write_csv(Path(args.out), selected)
    write_readme(Path(args.readme), selected, input_path)
    print("PASS")
    print(f"selected={len(selected)}")


if __name__ == "__main__":
    main()
