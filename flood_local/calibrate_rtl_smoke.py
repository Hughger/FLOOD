#!/usr/bin/env python3
"""Build a first RTL smoke calibration report from FLOOD Verilog runs.

The input table is produced by the Icarus Verilog smoke matrix.  These are
small, controlled RTL measurements.  The fitted expression is intentionally
simple and should be treated as a bring-up calibration, not a paper model.
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
    return int(fnum(value))


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


def predict_final_run_cycles(row: dict[str, str]) -> float:
    """Small empirical model fitted from the current smoke matrix.

    Baseline point: k=1, cout=1, group_size=4, final run = 35 cycles.
    The k=3/cout=2 point shows a strong interaction, so keep that term explicit.
    """
    k = fint(row["k"])
    cout = fint(row["cout"])
    group_size = fint(row["group_size"])
    k_extra = max(0, k - 1)
    cout_extra = max(0, cout - 1)
    group_extra = max(0, group_size - 4)
    high_group_extra = max(0, group_size - 8)
    return (
        35.0
        + 13.0 * cout_extra
        + 22.0 * k_extra
        + 20.5 * k_extra * cout_extra
        + 1.5 * group_extra
        + 0.375 * high_group_extra
        + 2.75 * k_extra * group_extra
    )


def predict_total_cycles(row: dict[str, str]) -> tuple[float, str]:
    cin_idx_total = max(1, fint(row["cin_idx_total"]))
    spatial_points = max(1, fint(row["res_cols"]) * fint(row["res_rows"]))
    final_cycles = predict_final_run_cycles(row)
    cycle_list: list[float] = []
    for _ in range(spatial_points):
        cycle_list.extend(final_cycles - 3.0 for _ in range(cin_idx_total - 1))
        cycle_list.append(final_cycles)
    return sum(cycle_list), ";".join(str(round(x, 4)) for x in cycle_list)


def build_details(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        predicted_total, predicted_list = predict_total_cycles(row)
        measured = fnum(row["total_cycles"])
        err = predicted_total - measured
        pct = err / measured * 100.0 if measured else 0.0
        item: dict[str, Any] = dict(row)
        item["predicted_cycle_list"] = predicted_list
        item["predicted_total_cycles"] = round(predicted_total, 4)
        item["error_cycles"] = round(err, 4)
        item["error_percent"] = round(pct, 4)
        out.append(item)
    return out


def build_summary(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    abs_errors = [abs(fnum(row["error_percent"])) for row in details]
    return [
        {
            "num_cases": len(details),
            "mean_abs_error_percent": round(sum(abs_errors) / len(abs_errors), 4) if abs_errors else 0,
            "max_abs_error_percent": round(max(abs_errors), 4) if abs_errors else 0,
            "mean_abs_error_cycles": round(
                sum(abs(fnum(row["error_cycles"])) for row in details) / len(details), 4
            )
            if details
            else 0,
            "model_scope": "FLOOD RTL smoke matrix only",
            "paper_ready": "no",
        }
    ]


def write_readme(path: Path, details: list[dict[str, Any]], summary: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# FLOOD RTL Smoke Calibration\n\n")
        fh.write("This report uses completed Icarus Verilog runs of `MacMachineWrapper.v`.\n\n")
        fh.write("## Current Equation\n\n")
        fh.write("For a final run:\n\n")
        fh.write("`cycles = 35 + 13*(cout-1) + 22*(k-1) + 20.5*(k-1)*(cout-1) + 1.5*max(group_size-4,0) + 0.375*max(group_size-8,0) + 2.75*(k-1)*max(group_size-4,0)`\n\n")
        fh.write("For multi-Cin cases, each non-final run currently uses `final_run_cycles - 3`.\n\n")
        fh.write("## Fit Quality\n\n")
        if summary:
            row = summary[0]
            fh.write(f"- cases: {row['num_cases']}\n")
            fh.write(f"- mean absolute error: {row['mean_abs_error_percent']}%\n")
            fh.write(f"- max absolute error: {row['max_abs_error_percent']}%\n")
        fh.write("\n## How To Use\n\n")
        fh.write("- Use this only as a bring-up calibration for the FLOOD RTL path.\n")
        fh.write("- Do not use it as final paper evidence until larger RTL cases are run.\n")
        fh.write("- Next useful cases: larger `cout`, larger `cin_idx_total`, `res_cols/res_rows > 1`, and representative workload layers.\n")
        fh.write("\n## Raw Cases\n\n")
        fh.write("| case | measured | predicted | error % |\n")
        fh.write("|---|---:|---:|---:|\n")
        for row in details:
            fh.write(
                f"| {row['case']} | {row['total_cycles']} | "
                f"{row['predicted_total_cycles']} | {row['error_percent']} |\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rows = list(csv.DictReader(open(args.input, newline="", encoding="utf-8")))
    details = build_details(rows)
    summary = build_summary(details)
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "rtl_smoke_calibration_details.csv", details)
    write_csv(out_dir / "rtl_smoke_calibration_summary.csv", summary)
    write_readme(out_dir / "README.md", details, summary)
    print(f"wrote RTL smoke calibration report to {out_dir}")


if __name__ == "__main__":
    main()
