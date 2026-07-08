#!/usr/bin/env python3
"""Smoke tests for real workload RTL expansion planning."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from build_real_workload_rtl_expansion_plan import build_plan


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_plan_prioritizes_clean_conv_tiles_and_blocks_no_output_cases() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate = root / "gate.csv"
        write_csv(
            gate,
            [
                {
                    "case_id": "calib_clean",
                    "dataset": "synthetic_unet_trace",
                    "source_id": "conv_clean",
                    "operator": "conv",
                    "shape_args": "1 32 32 64 64 3 1 1",
                    "k": "3",
                    "cout_blocks": "2",
                    "cin_idx_total": "1",
                    "res_cols": "1",
                    "res_rows": "4",
                    "stride": "1",
                    "run_count": "4",
                    "total_cycles": "532",
                    "rtl_subset_status": "rtl_complete_clean",
                },
                {
                    "case_id": "calib_partial",
                    "dataset": "workload_v1",
                    "source_id": "unet_large",
                    "operator": "conv",
                    "shape_args": "1 64 64 320 320 3 1 1",
                    "k": "3",
                    "cout_blocks": "8",
                    "cin_idx_total": "3",
                    "res_cols": "2",
                    "res_rows": "4",
                    "stride": "1",
                    "run_count": "2",
                    "total_cycles": "908",
                    "rtl_subset_status": "rtl_partial_progress_clean",
                },
                {
                    "case_id": "calib_gemm",
                    "dataset": "workload_v1",
                    "source_id": "dit_mlp",
                    "operator": "gemm",
                    "shape_args": "256 768 3072",
                    "k": "1",
                    "cout_blocks": "8",
                    "cin_idx_total": "6",
                    "res_cols": "4",
                    "res_rows": "1",
                    "stride": "1",
                    "run_count": "0",
                    "total_cycles": "NA",
                    "rtl_subset_status": "rtl_timeout_no_output",
                },
            ],
        )

        out_dir = root / "out"
        build_plan(gate, out_dir)

        manifest = read_csv(out_dir / "next_server_run_manifest.csv")
        by_case = {row["next_case_id"]: row for row in manifest}

        assert by_case["calib_clean_repeat"]["priority"] == "P0"
        assert by_case["calib_partial_safe_tile"]["cout_blocks"] == "2"
        assert by_case["calib_partial_safe_tile"]["cin_idx_total"] == "1"
        assert by_case["calib_partial_safe_tile"]["res_cols"] == "1"
        assert by_case["calib_partial_safe_tile"]["expected_policy"] == "likely_complete_tile"
        assert by_case["calib_gemm_bringup"]["priority"] == "P2"
        assert by_case["calib_gemm_bringup"]["expected_policy"] == "separate_testbench_bringup_required"

        summary = read_csv(out_dir / "rtl_expansion_plan_summary.csv")[0]
        assert summary["p0_tasks"] == "2"
        assert summary["p1_tasks"] == "1"
        assert summary["p2_tasks"] == "1"


if __name__ == "__main__":
    test_plan_prioritizes_clean_conv_tiles_and_blocks_no_output_cases()
    print("real workload RTL expansion plan smoke test passed")
