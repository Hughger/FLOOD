#!/usr/bin/env python3
"""Smoke tests for RTL tile-calibrated full-layer projection."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from build_rtl_tile_projection import build_projection


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_projection_uses_clean_tile_cycles_and_blocks_direct_paper_use() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = root / "gate.csv"
        plan = root / "plan.csv"
        write_csv(
            gate,
            [
                {
                    "next_case_id": "calib_09_safe_tile",
                    "source_case_id": "calib_09",
                    "dataset": "workload_v1",
                    "source_id": "unet_conv",
                    "operator": "conv",
                    "shape_args": "1 64 64 320 320 3 1 1",
                    "run_count": "4",
                    "total_cycles": "532",
                    "expansion_status": "rtl_expansion_complete_clean",
                    "ready_for_calibration": "yes",
                }
            ],
        )
        write_csv(
            plan,
            [
                {
                    "next_case_id": "calib_09_safe_tile",
                    "full_layer_tile_count_estimate": "240",
                    "priority": "P0",
                }
            ],
        )

        out_dir = root / "out"
        build_projection(gate, plan, out_dir)

        rows = read_csv(out_dir / "rtl_tile_full_layer_projection.csv")
        assert rows[0]["rtl_avg_cycles_per_tile_run"] == "133.00"
        assert rows[0]["rtl_tile_projected_mac_cycles"] == "31920"
        assert rows[0]["ready_for_direct_paper_data"] == "no"

        summary = read_csv(out_dir / "rtl_tile_projection_summary.csv")[0]
        assert summary["projected_rows"] == "1"
        assert summary["direct_paper_ready_rows"] == "0"


if __name__ == "__main__":
    test_projection_uses_clean_tile_cycles_and_blocks_direct_paper_use()
    print("RTL tile projection smoke test passed")
