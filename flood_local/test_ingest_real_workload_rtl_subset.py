#!/usr/bin/env python3
"""Tests for real-workload-derived RTL subset ingestion."""

from __future__ import annotations

import csv
from pathlib import Path

from ingest_real_workload_rtl_subset import ingest_subset


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_ingest_subset_classifies_complete_partial_timeout_and_error(tmp_path: Path) -> None:
    src = tmp_path / "server" / "real_workload_rtl_subset_v1.csv"
    rows = [
        {
            "case_id": "complete",
            "dataset": "workload_v1",
            "source_id": "unet_small",
            "operator": "conv",
            "rc": "0",
            "run_count": "4",
            "total_cycles": "532",
            "x_count": "0",
            "timeout": "no",
        },
        {
            "case_id": "partial",
            "dataset": "workload_v1",
            "source_id": "unet_large",
            "operator": "conv",
            "rc": "124",
            "run_count": "2",
            "total_cycles": "908",
            "x_count": "0",
            "timeout": "yes",
        },
        {
            "case_id": "timeout",
            "dataset": "workload_v1",
            "source_id": "dit_mlp",
            "operator": "gemm",
            "rc": "124",
            "run_count": "0",
            "total_cycles": "NA",
            "x_count": "0",
            "timeout": "yes",
        },
        {
            "case_id": "xcase",
            "dataset": "workload_v1",
            "source_id": "bad",
            "operator": "conv",
            "rc": "0",
            "run_count": "1",
            "total_cycles": "10",
            "x_count": "3",
            "timeout": "no",
        },
    ]
    write_csv(src, rows)

    out_dir = tmp_path / "out"
    ingest_subset(src, out_dir)

    gate = read_rows(out_dir / "real_workload_rtl_subset_gate.csv")
    status_by_case = {row["case_id"]: row["rtl_subset_status"] for row in gate}
    assert status_by_case == {
        "complete": "rtl_complete_clean",
        "partial": "rtl_partial_progress_clean",
        "timeout": "rtl_timeout_no_output",
        "xcase": "rtl_x_or_error",
    }

    summary = read_rows(out_dir / "real_workload_rtl_subset_summary.csv")[0]
    assert summary["total_cases"] == "4"
    assert summary["complete_clean_cases"] == "1"
    assert summary["partial_progress_clean_cases"] == "1"
    assert summary["timeout_no_output_cases"] == "1"
    assert summary["x_or_error_cases"] == "1"
    assert summary["paper_data_policy"] == "calibration_only_not_direct_paper_data"


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_ingest_subset_classifies_complete_partial_timeout_and_error(Path(tmp))
    print("real workload RTL subset ingest smoke test passed")
