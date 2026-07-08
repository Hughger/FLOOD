#!/usr/bin/env python3
"""Smoke tests for P1 RTL progress gate."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from build_rtl_p1_progress_gate import build_gate


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_p1_gate_counts_clean_progress_and_isolates_x_cases() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        gate_csv = root / "p1.csv"
        write_csv(
            gate_csv,
            [
                {"next_case_id": "clean", "expansion_status": "rtl_expansion_partial_clean", "run_count": "9", "x_count": "0"},
                {"next_case_id": "bad", "expansion_status": "rtl_expansion_x_or_error", "run_count": "10", "x_count": "4096"},
            ],
        )

        out_dir = root / "out"
        build_gate(gate_csv, out_dir)

        summary = read_csv(out_dir / "rtl_p1_progress_summary.csv")[0]
        assert summary["p1_progress_status"] == "partial_pass_with_isolated_x_cases"
        assert summary["clean_progress_cases"] == "1"
        assert summary["isolated_x_or_error_cases"] == "1"
        assert summary["direct_paper_ready_cases"] == "0"


if __name__ == "__main__":
    test_p1_gate_counts_clean_progress_and_isolates_x_cases()
    print("RTL P1 progress gate smoke test passed")
