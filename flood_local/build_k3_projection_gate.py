#!/usr/bin/env python3
"""Classify k3 workload projections against current RTL evidence limits."""
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
    return int(round(fnum(value)))


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


def classify(row: dict[str, str]) -> dict[str, Any]:
    k = fint(row.get("group16_v7_k"))
    cin = fint(row.get("group16_v7_cin_idx_total"))
    cout = fint(row.get("group16_v7_cout"))
    spatial = fint(row.get("group16_v7_spatial_points"))
    if k != 3:
        status = "not_k3"
        reason = "not a k3 projection row"
    elif cin <= 3 and cout <= 6 and spatial == 1:
        status = "within_direct_rtl_clean_k3_envelope"
        reason = "covered by current k3 fit/holdout envelope"
    elif cin == 2 and cout == 2 and spatial > 2:
        status = "appendix_projection_large_spatial_after_spatial2_clean"
        reason = "cout/cin match k3 spatial probes, but workload spatial exceeds direct-clean spatial=2 evidence"
    elif cin <= 3 and cout <= 6:
        status = "appendix_projection_spatial_extrapolation"
        reason = "cout/cin are inside k3 evidence envelope but workload spatial exceeds current direct-clean range"
    else:
        status = "appendix_projection_cin_or_cout_extrapolation"
        reason = "cin/cout exceed current k3 direct-clean fit/holdout envelope"
    out = {
        "id": row.get("id"),
        "dataset": row.get("dataset"),
        "shape_args": row.get("shape_args"),
        "cout": cout,
        "cin_idx_total": cin,
        "spatial_points": spatial,
        "pytorchsim_cycles": row.get("pytorchsim_cycles"),
        "group16_v7_cycles": row.get("group16_v7_total_cycles"),
        "k3_gate_status": status,
        "k3_gate_reason": reason,
    }
    return out


def write_readme(path: Path, rows: list[dict[str, Any]]) -> None:
    groups: dict[str, int] = {}
    for row in rows:
        groups[row["k3_gate_status"]] = groups.get(row["k3_gate_status"], 0) + 1
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# k3 projection gate v1\n\n")
        fh.write("## Purpose\n\n")
        fh.write(
            "This gate documents the remaining k3 projection rows after fast credibility tightening. "
            "Current RTL-clean k3 evidence covers res=1, cin<=3, cout<=6, plus cout=2/cin=2 spatial=2/4/8 probes. "
            "Workload k3 rows outside that envelope stay in appendix/projection, not the HPCA main table.\n\n"
        )
        fh.write("## Counts\n\n")
        for status, count in sorted(groups.items()):
            fh.write(f"- {status}: {count}\n")
        fh.write("\n## Rule\n\n")
        fh.write(
            "No k3 workload row is admitted to the main performance table unless it becomes direct RTL-clean. "
            "The current rows are useful as projection/diagnostic evidence only.\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    with open(args.workload, newline="", encoding="utf-8") as fh:
        rows = [
            classify(row)
            for row in csv.DictReader(fh)
            if row.get("group16_v7_adversarial_scope_status") == "C_projection_large_k3_extent_unvalidated"
        ]
    out_dir = Path(args.out_dir)
    write_csv(out_dir / "k3_projection_gate.csv", rows)
    write_readme(out_dir / "README.md", rows)
    print(f"wrote k3 projection gate to {out_dir}")


if __name__ == "__main__":
    main()
