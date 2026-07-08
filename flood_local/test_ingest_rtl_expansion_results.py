#!/usr/bin/env python3
"""Smoke tests for ingesting RTL expansion run logs."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from ingest_rtl_expansion_results import ingest_results


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_ingest_reparses_done_interrupt_cycles_from_logs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        raw = root / "raw.csv"
        log_dir = root / "server"
        log_dir.mkdir()
        (log_dir / "clean.log").write_text(
            "[TB] Done interrupt after 133 cycles at time 100\n"
            "[TB] Done interrupt after 133 cycles at time 200\n",
            encoding="utf-8",
        )
        write_csv(
            raw,
            [
                {
                    "next_case_id": "clean",
                    "priority": "P0",
                    "rc": "0",
                    "run_count": "0",
                    "cycle_list": "NA",
                    "total_cycles": "NA",
                    "x_count": "0",
                    "timeout": "no",
                    "log": "clean.log",
                }
            ],
        )

        out_dir = root / "out"
        ingest_results(raw, log_dir, out_dir)

        gate = read_csv(out_dir / "rtl_expansion_results_gate.csv")[0]
        assert gate["run_count"] == "2"
        assert gate["cycle_list"] == "133;133"
        assert gate["total_cycles"] == "266"
        assert gate["expansion_status"] == "rtl_expansion_complete_clean"

        summary = read_csv(out_dir / "rtl_expansion_results_summary.csv")[0]
        assert summary["complete_clean_cases"] == "1"
        assert summary["calibration_ready_cases"] == "1"
        assert summary["direct_paper_ready_cases"] == "0"


if __name__ == "__main__":
    test_ingest_reparses_done_interrupt_cycles_from_logs()
    print("RTL expansion results ingest smoke test passed")
