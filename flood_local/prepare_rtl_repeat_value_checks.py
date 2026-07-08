#!/usr/bin/env python3
"""Prepare value-check inputs from server RTL repeat runs."""

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


def successful_cases(status_rows: list[dict[str, str]]) -> list[str]:
    by_case: dict[str, set[str]] = {}
    for row in status_rows:
        if row.get("rc") == "0" and row.get("timeout") == "no":
            by_case.setdefault(row.get("case_id", ""), set()).add(row.get("pass_name", ""))
    return sorted(case for case, passes in by_case.items() if {"golden", "rtl"}.issubset(passes))


def concat_case_files(case_dir: Path, out_path: Path) -> int:
    files = sorted(case_dir.glob("actual_*.csv"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    value_files = 0
    with out_path.open("w", encoding="utf-8") as out:
        for src in files:
            text = src.read_text(encoding="utf-8", errors="ignore")
            if text.strip():
                out.write(text)
                if not text.endswith("\n"):
                    out.write("\n")
                value_files += 1
    return value_files


def prepare_checks(server_root: Path, out_dir: Path) -> None:
    status_rows = read_rows(server_root / "results" / "value_repeat_status.csv")
    manifest_rows: list[dict[str, str]] = []
    prepare_rows: list[dict[str, str]] = []
    for case in successful_cases(status_rows):
        golden_dir = server_root / "golden" / case
        rtl_dir = server_root / "rtl" / case
        golden_out = out_dir / "values" / case / "golden_values.txt"
        rtl_out = out_dir / "values" / case / "rtl_values.txt"
        golden_files = concat_case_files(golden_dir, golden_out)
        rtl_files = concat_case_files(rtl_dir, rtl_out)
        ready = golden_files > 0 and rtl_files > 0
        prepare_rows.append(
            {
                "case_id": case,
                "golden_files": str(golden_files),
                "rtl_files": str(rtl_files),
                "prepare_status": "ready" if ready else "missing_value_files",
                "evidence_scope": "server_rtl_repeatability_golden_vs_rtl",
            }
        )
        if ready:
            manifest_rows.append(
                {
                    "workload_id": case,
                    "golden_values": str(golden_out),
                    "rtl_values": str(rtl_out),
                    "out_subdir": case,
                    "rtol": "0.0",
                    "atol": "0.0",
                }
            )

    write_csv(out_dir / "value_repeat_manifest.csv", manifest_rows)
    write_csv(out_dir / "value_repeat_prepare_detail.csv", prepare_rows)
    write_csv(
        out_dir / "value_repeat_prepare_summary.csv",
        [
            {
                "prepare_status": "pass" if manifest_rows else "missing_input",
                "cases": str(len(prepare_rows)),
                "ready_cases": str(len(manifest_rows)),
                "evidence_scope": "server_rtl_repeatability_not_independent_software_golden",
                "paper_data_policy": "calibration_value_repeatability_only",
            }
        ],
    )
    readme = """# Server RTL Repeat Value Inputs

This directory prepares value-check inputs from two server RTL runs of the same
P0 tile cases. The first run is frozen as `golden_values.txt`; the second run is
treated as `rtl_values.txt`.

This proves deterministic RTL output repeatability for the captured tile cases.
It is not an independent software golden reference.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", default="results/flood_cycle_sim_v1/server_rtl_value_repeat_v1")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/rtl_value_repeat_prepare")
    args = parser.parse_args()
    prepare_checks(Path(args.server_root), Path(args.out_dir))


if __name__ == "__main__":
    main()
