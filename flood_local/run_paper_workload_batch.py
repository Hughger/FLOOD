#!/usr/bin/env python3
"""Run a manifest of FLOOD paper workloads and merge gated outputs."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


REQUIRED_COLUMNS = {
    "workload_id",
    "input_csv",
    "out_subdir",
    "include_system",
    "emit_paper_tables",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys or ["status"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_manifest(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise SystemExit("Manifest is empty.")
    missing = REQUIRED_COLUMNS - set(rows[0].keys())
    if missing:
        raise SystemExit(f"Manifest missing required columns: {', '.join(sorted(missing))}")


def run_one(row: dict[str, str], out_root: Path, cycle_trace_cap: str) -> dict[str, str]:
    workload_id = row["workload_id"].strip()
    input_csv = Path(row["input_csv"].strip())
    out_dir = out_root / row["out_subdir"].strip()
    cmd = [
        sys.executable,
        str(Path("flood_local") / "flood_cycle_sim.py"),
        "--input",
        str(input_csv),
        "--out-dir",
        str(out_dir),
        "--cycle-trace-cap",
        cycle_trace_cap,
    ]
    if truthy(row.get("include_system", "")):
        cmd.append("--include-system")
    if truthy(row.get("emit_paper_tables", "")):
        cmd.append("--emit-paper-tables")

    result = {
        "workload_id": workload_id,
        "input_csv": str(input_csv),
        "out_dir": str(out_dir),
        "run_status": "not_started",
        "returncode": "",
        "error": "",
    }
    if not input_csv.exists():
        result.update(
            {
                "run_status": "missing_input",
                "returncode": "NA",
                "error": f"input_csv not found: {input_csv}",
            }
        )
        return result

    proc = subprocess.run(cmd, text=True, capture_output=True)
    result["returncode"] = str(proc.returncode)
    if proc.returncode != 0:
        result["run_status"] = "failed"
        result["error"] = (proc.stderr or proc.stdout).strip().replace("\n", " ")[:500]
        return result

    result["run_status"] = "pass"
    return result


def prefix_rows(workload_id: str, source_file: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        merged = {"workload_id": workload_id, "source_file": source_file}
        merged.update(row)
        out.append(merged)
    return out


def merge_outputs(batch_results: list[dict[str, str]], out_root: Path) -> None:
    summary_rows: list[dict[str, str]] = []
    gate_rows: list[dict[str, str]] = []
    value_rows: list[dict[str, str]] = []

    for result in batch_results:
        workload_id = result["workload_id"]
        out_dir = Path(result["out_dir"])
        summary_rows.extend(prefix_rows(workload_id, "workload_summary.csv", read_csv_if_exists(out_dir / "workload_summary.csv")))
        gate_rows.extend(
            prefix_rows(
                workload_id,
                "paper_tables/fig3_evidence_gate.csv",
                read_csv_if_exists(out_dir / "paper_tables" / "fig3_evidence_gate.csv"),
            )
        )
        value_rows.extend(prefix_rows(workload_id, "value_check_summary.csv", read_csv_if_exists(out_dir / "value_check_summary.csv")))

    write_csv(out_root / "batch_run_status.csv", batch_results)
    write_csv(out_root / "merged_workload_summary.csv", summary_rows)
    write_csv(out_root / "merged_paper_gate.csv", gate_rows)
    write_csv(out_root / "merged_value_check_summary.csv", value_rows)

    ready_rows = []
    for result in batch_results:
        workload_id = result["workload_id"]
        gates = [r for r in gate_rows if r.get("workload_id") == workload_id]
        values = [r for r in value_rows if r.get("workload_id") == workload_id]
        policies = sorted({r.get("paper_use_policy", "missing") for r in gates}) or ["missing"]
        value_statuses = sorted({r.get("value_check_status", "missing") for r in values}) or ["missing"]
        main_rows = sum(1 for r in gates if r.get("paper_use_policy") == "candidate_for_main_performance_table")
        value_pass = value_statuses == ["pass"]
        gate_review_ready = result["run_status"] == "pass" and gates and "missing" not in policies
        main_ready = gate_review_ready and main_rows > 0 and value_pass
        blockers: list[str] = []
        if result["run_status"] != "pass":
            blockers.append("run_failed")
        if not gates:
            blockers.append("missing_paper_gate")
        if main_rows == 0:
            blockers.append("no_main_table_candidate_rows")
        if not value_pass:
            blockers.append("missing_or_failed_value_check")
        ready_rows.append(
            {
                "workload_id": workload_id,
                "run_status": result["run_status"],
                "main_table_candidate_rows": str(main_rows),
                "paper_use_policies": ";".join(policies),
                "value_check_statuses": ";".join(value_statuses),
                "batch_ready_policy": "ready_for_gate_review" if gate_review_ready else "not_ready",
                "main_figure_ready_policy": "ready_for_main_figure" if main_ready else "not_ready_for_main_figure",
                "main_figure_blockers": ";".join(blockers),
            }
        )
    write_csv(out_root / "batch_readiness_summary.csv", ready_rows)


def write_readme(out_root: Path, manifest: Path) -> None:
    text = f"""# FLOOD Paper Workload Batch

Manifest: `{manifest}`

Generated files:

- `batch_run_status.csv`: whether each workload ran.
- `merged_workload_summary.csv`: combined per-layer/workload cycle summaries.
- `merged_paper_gate.csv`: combined confidence grades and paper-use policies.
- `merged_value_check_summary.csv`: combined value-check status.
- `batch_readiness_summary.csv`: one row per workload for handoff review.

Rule for use: students may run this batch tool, but only rows passing the paper
gate and later value/system evidence checks should enter main paper figures.
"""
    (out_root / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--cycle-trace-cap", default="2000")
    args = parser.parse_args()

    manifest = Path(args.manifest)
    rows = read_rows(manifest)
    validate_manifest(rows)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    batch_results = [run_one(row, out_root, args.cycle_trace_cap) for row in rows]
    merge_outputs(batch_results, out_root)
    write_readme(out_root, manifest)
    failed = [row for row in batch_results if row["run_status"] != "pass"]
    if failed:
        raise SystemExit(f"{len(failed)} workload(s) did not run successfully. See batch_run_status.csv.")


if __name__ == "__main__":
    main()
