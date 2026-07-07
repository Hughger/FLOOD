#!/usr/bin/env python3
"""Run full-chip/system calibration checks from a manifest."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


REQUIRED_COLUMNS = {"calibration_id", "template_csv", "log_map_csv", "out_subdir"}


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
        raise SystemExit("Calibration manifest is empty.")
    missing = REQUIRED_COLUMNS - set(rows[0].keys())
    if missing:
        raise SystemExit(f"Calibration manifest missing required columns: {', '.join(sorted(missing))}")


def run_command(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    msg = (proc.stderr or proc.stdout).strip().replace("\n", " ")
    return proc.returncode, msg[:500]


def run_one(row: dict[str, str], out_root: Path) -> dict[str, str]:
    calibration_id = row["calibration_id"].strip()
    template_csv = Path(row["template_csv"].strip())
    log_map_csv = Path(row["log_map_csv"].strip())
    out_dir = out_root / row["out_subdir"].strip()
    parsed_csv = out_dir / "parsed_system_calibration.csv"

    result = {
        "calibration_id": calibration_id,
        "template_csv": str(template_csv),
        "log_map_csv": str(log_map_csv),
        "out_dir": str(out_dir),
        "run_status": "not_started",
        "parse_returncode": "",
        "calibration_returncode": "",
        "error": "",
    }
    if not template_csv.exists():
        result.update({"run_status": "missing_template", "error": f"missing template_csv: {template_csv}"})
        return result
    if not log_map_csv.exists():
        result.update({"run_status": "missing_log_map", "error": f"missing log_map_csv: {log_map_csv}"})
        return result

    out_dir.mkdir(parents=True, exist_ok=True)
    parse_cmd = [
        sys.executable,
        str(Path("flood_local") / "parse_system_calibration_logs.py"),
        "--template",
        str(template_csv),
        "--log-map",
        str(log_map_csv),
        "--out",
        str(parsed_csv),
    ]
    code, msg = run_command(parse_cmd)
    result["parse_returncode"] = str(code)
    if code != 0:
        result.update({"run_status": "parse_failed", "error": msg})
        return result

    calib_cmd = [
        sys.executable,
        str(Path("flood_local") / "flood_cycle_sim.py"),
        "--out-dir",
        str(out_dir),
        "--system-calibration",
        str(parsed_csv),
    ]
    system_model_csv = row.get("system_model_csv", "").strip()
    if system_model_csv:
        if not Path(system_model_csv).exists():
            result.update({"run_status": "missing_system_model", "error": f"missing system_model_csv: {system_model_csv}"})
            return result
        calib_cmd.extend(["--system-model", system_model_csv])

    code, msg = run_command(calib_cmd)
    result["calibration_returncode"] = str(code)
    if code != 0:
        result.update({"run_status": "calibration_failed", "error": msg})
        return result

    result["run_status"] = "pass"
    return result


def merge_outputs(results: list[dict[str, str]], out_root: Path) -> None:
    summary_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []
    parsed_rows: list[dict[str, str]] = []

    for result in results:
        calibration_id = result["calibration_id"]
        out_dir = Path(result["out_dir"])
        for row in read_rows_if_exists(out_dir / "system_calibration_summary.csv"):
            merged = {"calibration_id": calibration_id}
            merged.update(row)
            summary_rows.append(merged)
        for row in read_rows_if_exists(out_dir / "system_calibration_details.csv"):
            merged = {"calibration_id": calibration_id}
            merged.update(row)
            detail_rows.append(merged)
        for row in read_rows_if_exists(out_dir / "parsed_system_calibration.csv"):
            merged = {"calibration_id": calibration_id}
            merged.update(row)
            parsed_rows.append(merged)

    write_csv(out_root / "calibration_batch_status.csv", results)
    write_csv(out_root / "merged_system_calibration_summary.csv", summary_rows)
    write_csv(out_root / "merged_system_calibration_details.csv", detail_rows)
    write_csv(out_root / "merged_parsed_system_calibration.csv", parsed_rows)

    readiness_rows: list[dict[str, str]] = []
    for result in results:
        calibration_id = result["calibration_id"]
        summaries = [row for row in summary_rows if row.get("calibration_id") == calibration_id]
        if not summaries:
            readiness_rows.append(
                {
                    "calibration_id": calibration_id,
                    "run_status": result["run_status"],
                    "paper_system_timing_policy": "not_ready_for_main_figure",
                    "blockers": "missing_calibration_summary",
                }
            )
            continue
        row = summaries[0]
        measured = int(float(row.get("measured_rows", "0") or 0))
        mismatch = int(float(row.get("mismatch_rows", "0") or 0))
        missing = int(float(row.get("missing_measurement_rows", "0") or 0))
        errors = int(float(row.get("error_rows", "0") or 0))
        blockers: list[str] = []
        if result["run_status"] != "pass":
            blockers.append("batch_run_failed")
        if measured <= 0:
            blockers.append("no_measured_rows")
        if mismatch:
            blockers.append("mismatch_rows")
        if missing:
            blockers.append("missing_measurement_rows")
        if errors:
            blockers.append("error_rows")
        ready = result["run_status"] == "pass" and measured > 0 and mismatch == 0 and missing == 0 and errors == 0
        readiness_rows.append(
            {
                "calibration_id": calibration_id,
                "run_status": result["run_status"],
                "measured_rows": str(measured),
                "mismatch_rows": str(mismatch),
                "missing_measurement_rows": str(missing),
                "error_rows": str(errors),
                "paper_system_timing_policy": "ready_for_main_figure_system_timing" if ready else "not_ready_for_main_figure",
                "blockers": ";".join(blockers),
            }
        )
    write_csv(out_root / "calibration_readiness_summary.csv", readiness_rows)


def write_readme(out_root: Path, manifest: Path) -> None:
    text = f"""# FLOOD System Calibration Batch

Manifest: `{manifest}`

This batch turns full-chip RTL/testbench logs into measured phase-cycle rows,
then checks them against the simulator system model.

Generated files:

- `calibration_batch_status.csv`: parse/check command status.
- `merged_parsed_system_calibration.csv`: log-derived measured phase cycles.
- `merged_system_calibration_summary.csv`: pass/mismatch counts.
- `merged_system_calibration_details.csv`: per-row phase errors.
- `calibration_readiness_summary.csv`: paper system-timing gate.

Main-figure rule: use system timing only when `paper_system_timing_policy` is
`ready_for_main_figure_system_timing`.
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
        raise SystemExit(f"{len(failed)} calibration batch item(s) failed. See calibration_batch_status.csv.")


if __name__ == "__main__":
    main()
