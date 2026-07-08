#!/usr/bin/env python3
"""Smoke tests for gating RTL repeat value evidence."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from build_rtl_value_repeat_gate import build_gate


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_repeat_gate_passes_clean_repeatability_but_blocks_direct_paper_use() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        prepare = root / "prepare.csv"
        value = root / "value.csv"
        write_csv(prepare, [{"prepare_status": "pass", "ready_cases": "2"}])
        write_csv(
            value,
            [
                {"workload_id": "a", "value_check_status": "pass", "compared_values": "10", "num_mismatches": "0"},
                {"workload_id": "b", "value_check_status": "pass", "compared_values": "20", "num_mismatches": "0"},
            ],
        )

        out_dir = root / "out"
        build_gate(prepare, value, out_dir)

        summary = read_csv(out_dir / "rtl_value_repeat_gate_summary.csv")[0]
        assert summary["repeat_value_gate_status"] == "pass"
        assert summary["passed_cases"] == "2"
        assert summary["direct_paper_ready_cases"] == "0"
        assert summary["paper_data_policy"] == "repeatability_only_not_independent_golden"


if __name__ == "__main__":
    test_repeat_gate_passes_clean_repeatability_but_blocks_direct_paper_use()
    print("RTL value repeat gate smoke test passed")
