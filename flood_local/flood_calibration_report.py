#!/usr/bin/env python3
"""Report FLOOD backend model error after RTL simulation calibration.

Input is the `calibration_cases.csv` produced by flood_backend_pipeline.py.
Fill the `rtl_sim_cycles` column after running RTL simulation, then run this
script to generate an error table and grouped summary.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


def fnum(value: Any) -> float:
    if value in ("", None):
        return 0.0
    return float(value)


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


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("status") != "calibrated":
            continue
        groups.setdefault(str(row.get("rtl_workmode_class", "")), []).append(row)

    out: list[dict[str, Any]] = []
    for workmode, items in sorted(groups.items()):
        abs_errors = [abs(fnum(r["error_percent"])) for r in items]
        signed_errors = [fnum(r["error_percent"]) for r in items]
        ratios = [fnum(r["rtl_to_model_ratio"]) for r in items]
        out.append(
            {
                "rtl_workmode_class": workmode,
                "num_cases": len(items),
                "mean_abs_error_percent": round(sum(abs_errors) / len(abs_errors), 4),
                "max_abs_error_percent": round(max(abs_errors), 4),
                "mean_signed_error_percent": round(sum(signed_errors) / len(signed_errors), 4),
                "mean_rtl_to_model_ratio": round(sum(ratios) / len(ratios), 6),
                "suggested_scale_factor": round(sum(ratios) / len(ratios), 6),
            }
        )
    return out


def write_readme(path: Path, details: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    calibrated = [r for r in details if r.get("status") == "calibrated"]
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD Backend Calibration Report\n\n")
        if not calibrated:
            fh.write("No rows have `rtl_sim_cycles` filled yet. Run RTL simulation for the cases in `calibration_cases.csv` first.\n")
            return
        fh.write("## Summary\n\n")
        fh.write("| Workmode | Cases | Mean abs error % | Max abs error % | Suggested scale |\n")
        fh.write("|---|---:|---:|---:|---:|\n")
        for row in summary:
            fh.write(
                f"| {row['rtl_workmode_class']} | {row['num_cases']} | "
                f"{row['mean_abs_error_percent']} | {row['max_abs_error_percent']} | "
                f"{row['suggested_scale_factor']} |\n"
            )
        fh.write("\n## Interpretation\n\n")
        fh.write("- `suggested_scale_factor > 1` means RTL simulation is slower than the current model for that workmode.\n")
        fh.write("- `suggested_scale_factor < 1` means RTL simulation is faster than the current model for that workmode.\n")
        fh.write("- Keep the raw calibration table in the paper appendix or artifact package if this model supports main results.\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = list(csv.DictReader(open(args.input, newline="", encoding="utf-8")))
    details: list[dict[str, Any]] = []
    for row in rows:
        predicted = fnum(row.get("model_predicted_cycles"))
        rtl = fnum(row.get("rtl_sim_cycles"))
        out = dict(row)
        if predicted and rtl:
            error = (predicted - rtl) / rtl * 100.0
            out["error_percent"] = round(error, 4)
            out["rtl_to_model_ratio"] = round(rtl / predicted, 6)
            out["status"] = "calibrated"
        else:
            out["status"] = "missing_rtl_sim_cycles"
        details.append(out)

    summary = summarize(details)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "calibration_error_details.csv", details)
    write_csv(out_dir / "calibration_error_summary.csv", summary)
    write_readme(out_dir / "calibration_report.md", details, summary)
    print(f"wrote calibration report to {out_dir}")


if __name__ == "__main__":
    main()
