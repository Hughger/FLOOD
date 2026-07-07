#!/usr/bin/env python3
"""Check cycle/system interval timelines for internal consistency."""

from __future__ import annotations

import argparse
import csv
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


def by_workload(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        wid = row.get("workload_id") or row.get("id") or ""
        if wid:
            out.setdefault(wid, []).append(row)
    return out


def check_intervals(
    result_dir: Path,
    table_name: str,
    interval_rows: list[dict[str, str]],
    summary_by_id: dict[str, dict[str, str]],
    summary_total_key: str,
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    grouped = by_workload(interval_rows)
    for workload_id, rows in sorted(grouped.items()):
        sorted_rows = sorted(rows, key=lambda r: (to_int(r, "start_cycle"), to_int(r, "end_cycle_exclusive")))
        issues: list[str] = []
        expected_start = 0
        last_end = 0
        total_duration = 0
        for idx, row in enumerate(sorted_rows):
            start = to_int(row, "start_cycle")
            duration = to_int(row, "duration_cycles")
            end = to_int(row, "end_cycle_exclusive")
            if duration < 0:
                issues.append(f"negative_duration_at_{idx}")
            if start < 0 or end < 0:
                issues.append(f"negative_cycle_at_{idx}")
            if end - start != duration:
                issues.append(f"duration_mismatch_at_{idx}")
            if start != expected_start:
                issues.append(f"non_contiguous_at_{idx}_expected_{expected_start}_got_{start}")
            expected_start = end
            last_end = end
            total_duration += duration
        summary = summary_by_id.get(workload_id, {})
        summary_total = to_int(summary, summary_total_key, -1)
        if summary and summary_total != last_end:
            issues.append(f"summary_total_mismatch_{summary_total_key}_expected_{summary_total}_got_{last_end}")
        if total_duration != last_end:
            issues.append(f"duration_sum_mismatch_sum_{total_duration}_got_{last_end}")
        checks.append(
            {
                "result_dir": str(result_dir),
                "table": table_name,
                "workload_id": workload_id,
                "interval_rows": str(len(rows)),
                "timeline_start": str(sorted_rows[0].get("start_cycle", "")) if sorted_rows else "",
                "timeline_end": str(last_end),
                "summary_total_key": summary_total_key,
                "summary_total": str(summary_total if summary else ""),
                "status": "pass" if not issues else "fail",
                "issues": ";".join(issues),
            }
        )
    return checks


def build_report(result_dirs: list[Path], out_dir: Path) -> None:
    all_checks: list[dict[str, str]] = []
    for result_dir in result_dirs:
        summary_rows = read_rows(result_dir / "workload_summary.csv")
        summary_by_id = {row.get("id", ""): row for row in summary_rows if row.get("id")}
        cycle_rows = read_rows(result_dir / "cycle_intervals.csv")
        system_rows = read_rows(result_dir / "system_intervals.csv")
        if cycle_rows:
            all_checks.extend(check_intervals(result_dir, "cycle_intervals", cycle_rows, summary_by_id, "total_cycles"))
        if system_rows:
            all_checks.extend(check_intervals(result_dir, "system_intervals", system_rows, summary_by_id, "system_total_cycles"))
        if not cycle_rows and not system_rows:
            all_checks.append(
                {
                    "result_dir": str(result_dir),
                    "table": "missing_intervals",
                    "workload_id": "",
                    "interval_rows": "0",
                    "timeline_start": "",
                    "timeline_end": "",
                    "summary_total_key": "",
                    "summary_total": "",
                    "status": "fail",
                    "issues": "no_cycle_or_system_intervals",
                }
            )
    write_csv(out_dir / "timeline_checks.csv", all_checks)
    failed = [row for row in all_checks if row.get("status") != "pass"]
    summary = [
        {
            "checked_rows": str(len(all_checks)),
            "passed_rows": str(len(all_checks) - len(failed)),
            "failed_rows": str(len(failed)),
            "checked_result_dirs": str(len(result_dirs)),
            "policy": "All timeline checks must pass before using generated cycle tables for batch analysis.",
        }
    ]
    write_csv(out_dir / "timeline_summary.csv", summary)
    text = f"""# FLOOD Timeline Consistency Report

This report checks internal consistency of generated cycle timelines. It does
not prove RTL correctness, but it catches broken interval accounting before
paper data is exported.

Generated files:

- `timeline_checks.csv`: per-workload interval checks.
- `timeline_summary.csv`: pass/fail counts.

Rule: `failed_rows` must be 0 before generated cycle tables are used.
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("result_dirs", nargs="+")
    args = parser.parse_args()
    build_report([Path(p) for p in args.result_dirs], Path(args.out_dir))


if __name__ == "__main__":
    main()
