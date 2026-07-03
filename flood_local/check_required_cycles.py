#!/usr/bin/env python3
"""Report workload rows with missing or invalid PyTorchSim cycles."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def valid_nonnegative_number(value: str) -> bool:
    if value.strip() == "":
        return False
    try:
        return float(value) >= 0
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    bad_rows: list[tuple[int, str, str]] = []
    for idx, row in enumerate(rows, start=2):
        cycles = (row.get("pytorchsim_cycles") or "").strip()
        if not valid_nonnegative_number(cycles):
            bad_rows.append((idx, row.get("id", ""), cycles))

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        fh.write("# PyTorchSim Cycles Check\n\n")
        fh.write(f"CSV: `{csv_path}`\n\n")
        fh.write(f"Rows: {len(rows)}\n\n")
        if bad_rows:
            fh.write("## Missing Or Invalid Cycles\n\n")
            fh.write("| line | id | pytorchsim_cycles |\n")
            fh.write("|---:|---|---|\n")
            for line_no, row_id, cycles in bad_rows:
                fh.write(f"| {line_no} | `{row_id}` | `{cycles}` |\n")
        else:
            fh.write("PASS\n")

    if bad_rows:
        print("FAILED")
        print(f"missing_or_invalid={len(bad_rows)}")
        raise SystemExit(1)
    print("PASS")
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
