#!/usr/bin/env python3
"""Run output-value checks for a batch of FLOOD workloads."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


REQUIRED_COLUMNS = {"workload_id", "golden_values", "rtl_values", "out_subdir"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_rows_if_exists(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_rows(path)


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


def validate_manifest(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise SystemExit("Value-check manifest is empty.")
    missing = REQUIRED_COLUMNS - set(rows[0].keys())
    if missing:
        raise SystemExit(f"Value-check manifest missing required columns: {', '.join(sorted(missing))}")


def clean_float(value: str, default: str) -> str:
    value = str(value).strip()
    if not value:
        return default
    float(value)
    return value


def run_one(row: dict[str, str], out_root: Path) -> dict[str, str]:
    workload_id = row["workload_id"].strip()
    golden = Path(row["golden_values"].strip())
    rtl = Path(row["rtl_values"].strip())
    out_dir = out_root / row["out_subdir"].strip()
    rtol = clean_float(row.get("rtol", ""), "0.0")
    atol = clean_float(row.get("atol", ""), "0.0")
    result = {
        "workload_id": workload_id,
        "golden_values": str(golden),
        "rtl_values": str(rtl),
        "out_dir": str(out_dir),
        "rtol": rtol,
        "atol": atol,
        "run_status": "not_started",
        "returncode": "",
        "error": "",
    }
    if not golden.exists():
        result.update({"run_status": "missing_golden", "error": f"missing golden_values: {golden}"})
        return result
    if not rtl.exists():
        result.update({"run_status": "missing_rtl", "error": f"missing rtl_values: {rtl}"})
        return result

    cmd = [
        sys.executable,
        str(Path("flood_local") / "flood_cycle_sim.py"),
        "--out-dir",
        str(out_dir),
        "--value-check-only",
        "--golden-values",
        str(golden),
        "--rtl-values",
        str(rtl),
        "--value-rtol",
        rtol,
        "--value-atol",
        atol,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    result["returncode"] = str(proc.returncode)
    if proc.returncode != 0:
        result.update(
            {
                "run_status": "checker_failed",
                "error": (proc.stderr or proc.stdout).strip().replace("\n", " ")[:500],
            }
        )
        return result
    result["run_status"] = "pass"
    return result


def merge_outputs(results: list[dict[str, str]], out_root: Path) -> None:
    summary_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []
    readiness_rows: list[dict[str, str]] = []

    for result in results:
        workload_id = result["workload_id"]
        out_dir = Path(result["out_dir"])
        summaries = read_rows_if_exists(out_dir / "value_check_summary.csv")
        for row in summaries:
            merged = {"workload_id": workload_id}
            merged.update(row)
            summary_rows.append(merged)
        for row in read_rows_if_exists(out_dir / "value_check_details.csv"):
            merged = {"workload_id": workload_id}
            merged.update(row)
            detail_rows.append(merged)

        status = summaries[0].get("value_check_status", "missing_summary") if summaries else "missing_summary"
        blockers: list[str] = []
        if result["run_status"] != "pass":
            blockers.append(result["run_status"])
        if status != "pass":
            blockers.append(f"value_check_status={status}")
        readiness_rows.append(
            {
                "workload_id": workload_id,
                "run_status": result["run_status"],
                "value_check_status": status,
                "main_value_ready_policy": "ready_for_main_figure_value" if result["run_status"] == "pass" and status == "pass" else "not_ready_for_main_figure",
                "blockers": ";".join(blockers),
            }
        )

    write_csv(out_root / "value_batch_status.csv", results)
    write_csv(out_root / "merged_value_check_summary.csv", summary_rows)
    write_csv(out_root / "merged_value_check_details.csv", detail_rows)
    write_csv(out_root / "value_readiness_summary.csv", readiness_rows)


def write_readme(out_root: Path, manifest: Path) -> None:
    text = f"""# FLOOD Value Check Batch

Manifest: `{manifest}`

This batch compares golden numeric outputs with RTL/testbench numeric outputs.
The checker is format-light: it extracts numeric tokens and compares them with
the requested tolerances.

Generated files:

- `value_batch_status.csv`: whether each checker run executed.
- `merged_value_check_summary.csv`: combined pass/fail/missing status.
- `merged_value_check_details.csv`: mismatching numeric positions when present.
- `value_readiness_summary.csv`: paper value-correctness gate.

Main-figure rule: use a workload only when `main_value_ready_policy` is
`ready_for_main_figure_value`.
"""
    (out_root / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()

    manifest = Path(args.manifest)
    rows = read_rows(manifest)
    validate_manifest(rows)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    results = [run_one(row, out_root) for row in rows]
    merge_outputs(results, out_root)
    write_readme(out_root, manifest)
    failed = [row for row in results if row.get("run_status") != "pass"]
    if failed:
        raise SystemExit(f"{len(failed)} value-check batch item(s) failed. See value_batch_status.csv.")


if __name__ == "__main__":
    main()
