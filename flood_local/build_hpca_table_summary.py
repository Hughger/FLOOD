#!/usr/bin/env python3
"""Create a concise HPCA-facing table summary from submission gates."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fnum(value: str) -> float:
    return float(value or 0)


def total(rows: list[dict[str, str]], field: str) -> float:
    return sum(fnum(row.get(field, "0")) for row in rows)


def write_summary(path: Path, main: list[dict[str, str]], appendix: list[dict[str, str]], blocked: list[dict[str, str]]) -> None:
    main_base = total(main, "pytorchsim_cycles")
    main_flood = total(main, "group16_v7_cycles")
    main_speedup = main_base / main_flood if main_flood else 0.0
    appendix_base = total(appendix, "pytorchsim_cycles")
    appendix_flood = total(appendix, "group16_v7_cycles")
    appendix_speedup = appendix_base / appendix_flood if appendix_flood else 0.0

    with path.open("w", encoding="utf-8") as fh:
        fh.write("# HPCA table summary v1\n\n")
        fh.write("## Main Table\n\n")
        fh.write("| scope | rows | PyTorchSim cycles | FLOOD cycles | speedup |\n")
        fh.write("|---|---:|---:|---:|---:|\n")
        fh.write(f"| direct RTL-clean only | {len(main)} | {main_base:.4f} | {main_flood:.4f} | {main_speedup:.6f} |\n\n")
        fh.write("Main-table claim: all rows are direct RTL-clean and XPROBE-clean. No C/D rows are included.\n\n")
        fh.write("## Appendix Projection\n\n")
        fh.write("| scope | rows | PyTorchSim cycles | FLOOD projected cycles | ratio |\n")
        fh.write("|---|---:|---:|---:|---:|\n")
        fh.write(
            f"| k3 projection only | {len(appendix)} | {appendix_base:.4f} | {appendix_flood:.4f} | {appendix_speedup:.6f} |\n\n"
        )
        fh.write("Appendix claim: projection rows are not main performance evidence. They are labeled as calibrated projections.\n\n")
        fh.write("## Excluded / Blocked\n\n")
        fh.write(f"- blocked/excluded rows: {len(blocked)}\n")
        fh.write("- reason: direct blocked, XPROBE boundary, unsupported operator, or known extrapolation boundary.\n\n")
        fh.write("## Paper wording\n\n")
        fh.write(
            "Use: The main performance table reports only direct RTL-clean workload rows. "
            "Additional k3 results are reported separately as calibrated projections with explicit scope limits.\n\n"
        )
        fh.write(
            "Avoid: The full workload is RTL validated; all projection rows are equivalent to direct RTL measurements.\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    gate = Path(args.gate_dir)
    write_summary(
        Path(args.out),
        read_csv(str(gate / "main_table_rows.csv")),
        read_csv(str(gate / "appendix_projection_rows.csv")),
        read_csv(str(gate / "blocked_or_excluded_rows.csv")),
    )
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
