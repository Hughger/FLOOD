#!/usr/bin/env python3
"""Build validation coverage and next-RTL-run priority reports."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["status"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def to_int(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, default)))
    except (TypeError, ValueError):
        return default


def workload_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("operator", ""),
        row.get("k", ""),
        row.get("cin_idx_total", ""),
        row.get("spatial_points", ""),
    )


def evidence_bucket(row: dict[str, str]) -> str:
    grade = row.get("confidence_grade", "")
    if grade.startswith("A_") or grade.startswith("B_"):
        return "main_candidate_or_direct"
    if grade.startswith("C_"):
        return "projection_only"
    if grade.startswith("D_"):
        return "blocked_or_excluded"
    return "unknown"


def build_matrix(results_root: Path, out_dir: Path, workload_dirs: list[str]) -> None:
    rtl_details = read_rows(results_root / "rtl_validation" / "rtl_validation_details.csv")
    rtl_blocked = read_rows(results_root / "rtl_validation" / "rtl_blocked_cases.csv")
    clean_shapes = {
        (row.get("k", ""), row.get("cout", ""), row.get("cin_idx_total", ""), row.get("spatial_points", ""))
        for row in rtl_details
        if row.get("validation_status") == "pass"
    }
    blocked_shapes = {
        (row.get("k", ""), row.get("cout", ""), row.get("cin_idx_total", ""), row.get("spatial_points", ""))
        for row in rtl_blocked
    }

    workload_rows: list[dict[str, str]] = []
    for name in workload_dirs:
        for row in read_rows(results_root / name / "workload_summary.csv"):
            row = dict(row)
            row["result_dir"] = name
            workload_rows.append(row)

    aggregate: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    detailed_rows: list[dict[str, str]] = []
    priority_rows: list[dict[str, str]] = []

    for row in workload_rows:
        shape = (row.get("k", ""), row.get("cout", ""), row.get("cin_idx_total", ""), row.get("spatial_points", ""))
        clean_hit = shape in clean_shapes
        blocked_hit = shape in blocked_shapes
        bucket = evidence_bucket(row)
        operator = row.get("operator", "")
        confidence = row.get("confidence_grade", "")
        aggregate[(row.get("result_dir", ""), operator, bucket)]["rows"] += 1
        aggregate[(row.get("result_dir", ""), operator, bucket)]["total_cycles"] += to_int(row, "total_cycles")
        if clean_hit:
            aggregate[(row.get("result_dir", ""), operator, bucket)]["direct_clean_shape_hits"] += 1
        if blocked_hit:
            aggregate[(row.get("result_dir", ""), operator, bucket)]["blocked_shape_hits"] += 1

        blockers: list[str] = []
        if not clean_hit:
            blockers.append("no_direct_clean_shape_match")
        if bucket != "main_candidate_or_direct":
            blockers.append(f"confidence={confidence or 'missing'}")
        if row.get("system_model_status") != "full_chip_rtl_calibrated":
            blockers.append(f"system={row.get('system_model_status', 'missing')}")
        if blocked_hit:
            blockers.append("similar_shape_has_blocked_x_or_zero_evidence")

        priority = "P0_run_full_chip_value_and_timing" if bucket == "projection_only" and not blocked_hit else "P1_fix_blocked_or_excluded" if blocked_hit or bucket == "blocked_or_excluded" else "P2_review"
        detailed_rows.append(
            {
                "result_dir": row.get("result_dir", ""),
                "workload_id": row.get("id", ""),
                "operator": operator,
                "source_stage": row.get("source_stage", ""),
                "shape_args": row.get("shape_args", ""),
                "k": row.get("k", ""),
                "cout": row.get("cout", ""),
                "cin_idx_total": row.get("cin_idx_total", ""),
                "spatial_points": row.get("spatial_points", ""),
                "total_cycles": row.get("total_cycles", ""),
                "confidence_grade": confidence,
                "evidence_bucket": bucket,
                "direct_clean_shape_match": str(clean_hit),
                "blocked_shape_match": str(blocked_hit),
                "system_model_status": row.get("system_model_status", ""),
                "next_validation_priority": priority,
                "blockers": ";".join(blockers),
            }
        )
        if priority != "P2_review":
            priority_rows.append(detailed_rows[-1])

    aggregate_rows: list[dict[str, str]] = []
    for (result_dir, operator, bucket), counts in sorted(aggregate.items()):
        aggregate_rows.append(
            {
                "result_dir": result_dir,
                "operator": operator,
                "evidence_bucket": bucket,
                "rows": str(counts["rows"]),
                "total_cycles": str(counts["total_cycles"]),
                "direct_clean_shape_hits": str(counts["direct_clean_shape_hits"]),
                "blocked_shape_hits": str(counts["blocked_shape_hits"]),
            }
        )

    priority_rows = sorted(
        priority_rows,
        key=lambda r: (
            0 if r["next_validation_priority"].startswith("P0") else 1,
            -to_int(r, "total_cycles"),
            r["workload_id"],
        ),
    )

    write_csv(out_dir / "validation_coverage_detail.csv", detailed_rows)
    write_csv(out_dir / "validation_coverage_summary.csv", aggregate_rows)
    write_csv(out_dir / "next_rtl_validation_priority.csv", priority_rows[:50])

    p0 = sum(1 for row in priority_rows if row["next_validation_priority"].startswith("P0"))
    p1 = sum(1 for row in priority_rows if row["next_validation_priority"].startswith("P1"))
    summary = [
        {
            "workload_rows": str(len(workload_rows)),
            "coverage_summary_rows": str(len(aggregate_rows)),
            "priority_rows_total": str(len(priority_rows)),
            "p0_rows": str(p0),
            "p1_rows": str(p1),
            "direct_clean_shapes": str(len(clean_shapes)),
            "blocked_shapes": str(len(blocked_shapes)),
            "policy": "Use next_rtl_validation_priority.csv to select the next full-chip RTL/value calibration targets.",
        }
    ]
    write_csv(out_dir / "coverage_readiness_summary.csv", summary)
    readme = """# FLOOD Validation Coverage Matrix

This report summarizes which generated workload rows are backed by direct clean
RTL shape evidence, which are projection-only, and which overlap blocked/X
evidence.

Generated files:

- `validation_coverage_detail.csv`: one row per workload.
- `validation_coverage_summary.csv`: aggregate by result directory/operator/evidence bucket.
- `next_rtl_validation_priority.csv`: top rows to run next in full-chip RTL/value validation.
- `coverage_readiness_summary.csv`: compact counts.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", default="results/flood_cycle_sim_v1")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/validation_coverage")
    parser.add_argument("--workload-dir", action="append", default=[])
    args = parser.parse_args()
    workload_dirs = args.workload_dir or ["person2_gemm", "synthetic_unet_trace", "softmax_smoke"]
    build_matrix(Path(args.results_root), Path(args.out_dir), workload_dirs)


if __name__ == "__main__":
    main()
