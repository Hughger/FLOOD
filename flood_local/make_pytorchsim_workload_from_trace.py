#!/usr/bin/env python3
"""Convert traced Diffusion operator shapes to a PyTorchSim workload table."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-rows-per-op", type=int, default=40)
    args = parser.parse_args()

    trace_path = Path(args.trace)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    counts = {"conv": 0, "gemm": 0}
    rows = []
    with trace_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            op = row.get("operator", "")
            if op not in counts:
                continue
            if counts[op] >= args.max_rows_per_op:
                continue
            counts[op] += 1
            rows.append(
                {
                    "id": f"{op}_{counts[op]:03d}_{row.get('op_id', '')}",
                    "workload": "SD15_UNet_trace",
                    "stage": row.get("module_name", ""),
                    "operator": op,
                    "shape_args": row.get("pytorchsim_shape_args", ""),
                    "shape_desc": row.get("note", ""),
                    "reason": "traced from real UNet forward pass",
                    "max_expected_runtime_s": "300",
                }
            )

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "workload",
                "stage",
                "operator",
                "shape_args",
                "shape_desc",
                "reason",
                "max_expected_runtime_s",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {out_path} with {len(rows)} workload rows")


if __name__ == "__main__":
    main()
