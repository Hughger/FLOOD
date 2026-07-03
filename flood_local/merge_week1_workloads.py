#!/usr/bin/env python3
"""Merge week-1 student workload CSV files into one canonical CSV."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

REQUIRED_COLUMNS = [
    "id",
    "model",
    "stage",
    "operator",
    "shape_args",
    "pytorchsim_cycles",
    "latency_us",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: missing header")
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(missing)}")
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({col: (row.get(col) or "").strip() for col in REQUIRED_COLUMNS})
        return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, rows: list[dict[str, str]], errors: list[str], inputs: list[Path]) -> None:
    op_counts: dict[str, int] = {}
    for row in rows:
        op = row.get("operator", "")
        op_counts[op] = op_counts.get(op, 0) + 1
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# Week 1 Workload Merge Report\n\n")
        fh.write("## Inputs\n\n")
        for input_path in inputs:
            fh.write(f"- `{input_path}`\n")
        fh.write(f"\nRows: {len(rows)}\n\n")
        fh.write("## Operator Counts\n\n")
        for op, count in sorted(op_counts.items()):
            fh.write(f"- `{op}`: {count}\n")
        fh.write("\n## Result\n\n")
        if errors:
            fh.write("FAILED\n\n")
            for error in errors:
                fh.write(f"- {error}\n")
        else:
            fh.write("PASS\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--allow-duplicate-identical", action="store_true")
    args = parser.parse_args()

    inputs = [Path(item) for item in args.inputs]
    merged: list[dict[str, str]] = []
    errors: list[str] = []
    by_id: dict[str, dict[str, str]] = {}

    for input_path in inputs:
        try:
            rows = read_csv(input_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        for row in rows:
            row_id = row["id"]
            if row_id in by_id:
                if args.allow_duplicate_identical and row == by_id[row_id]:
                    continue
                errors.append(f"duplicate id across files: {row_id}")
                continue
            by_id[row_id] = row
            merged.append(row)

    merged.sort(key=lambda row: row["id"])
    write_csv(Path(args.out), merged)
    write_report(Path(args.report), merged, errors, inputs)

    if errors:
        print("FAILED")
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("PASS")
    print(f"rows={len(merged)}")


if __name__ == "__main__":
    main()
