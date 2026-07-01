#!/usr/bin/env python3
"""Validate team PyTorchSim workload CSV files."""
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

ALLOWED_OPERATORS = {"conv", "gemm", "softmax"}


def is_number(value: str) -> bool:
    if value == "":
        return True
    try:
        float(value)
        return True
    except ValueError:
        return False


def parse_ints(value: str) -> list[int] | None:
    try:
        return [int(x) for x in value.strip().split()]
    except ValueError:
        return None


def validate_shape(operator: str, shape_args: str) -> str | None:
    dims = parse_ints(shape_args)
    if dims is None:
        return "shape_args must contain integers separated by spaces"
    if operator == "conv":
        if len(dims) != 8:
            return "conv shape_args must be: B H W IC OC K S P"
        b, h, w, ic, oc, k, stride, pad = dims
        if min(b, h, w, ic, oc, k, stride) <= 0:
            return "conv B/H/W/IC/OC/K/S must be positive"
        if pad < 0:
            return "conv padding must be non-negative"
        return None
    if operator == "gemm":
        if len(dims) != 3:
            return "gemm shape_args must be: M K N"
        if min(dims) <= 0:
            return "gemm M/K/N must be positive"
        return None
    if operator == "softmax":
        if len(dims) != 1:
            return "softmax shape_args must be: N"
        if dims[0] <= 0:
            return "softmax N must be positive"
        return None
    return f"unsupported operator: {operator}"


def validate(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return [], ["CSV has no header"]
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            errors.append(f"missing columns: {', '.join(missing)}")
        rows = list(reader)

    seen_ids: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        row_id = (row.get("id") or "").strip()
        if not row_id:
            errors.append(f"line {idx}: id is empty")
        elif row_id in seen_ids:
            errors.append(f"line {idx}: duplicate id '{row_id}'")
        seen_ids.add(row_id)

        for col in ["model", "stage", "operator", "shape_args", "pytorchsim_cycles"]:
            if not (row.get(col) or "").strip():
                errors.append(f"line {idx}: {col} is empty")

        operator = (row.get("operator") or "").strip()
        if operator not in ALLOWED_OPERATORS:
            errors.append(f"line {idx}: operator must be one of {sorted(ALLOWED_OPERATORS)}")
            continue

        shape_error = validate_shape(operator, row.get("shape_args") or "")
        if shape_error:
            errors.append(f"line {idx}: {shape_error}")

        cycles = (row.get("pytorchsim_cycles") or "").strip()
        if not is_number(cycles) or float(cycles or 0) < 0:
            errors.append(f"line {idx}: pytorchsim_cycles must be a non-negative number")

        latency = (row.get("latency_us") or "").strip()
        if latency and (not is_number(latency) or float(latency) < 0):
            errors.append(f"line {idx}: latency_us must be empty or a non-negative number")

    return rows, errors


def write_report(path: Path, csv_path: Path, rows: list[dict[str, str]], errors: list[str]) -> None:
    op_counts: dict[str, int] = {}
    for row in rows:
        op = row.get("operator", "")
        op_counts[op] = op_counts.get(op, 0) + 1
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# Workload CSV Check Report\n\n")
        fh.write(f"CSV: `{csv_path}`\n\n")
        fh.write(f"Rows: {len(rows)}\n\n")
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
    parser.add_argument("csv_path")
    parser.add_argument("--report")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    rows, errors = validate(csv_path)
    if args.report:
        write_report(Path(args.report), csv_path, rows, errors)

    if errors:
        print("FAILED")
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("PASS")
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
