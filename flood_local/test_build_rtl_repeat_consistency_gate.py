#!/usr/bin/env python3
"""Smoke tests for RTL repeat consistency gates."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from build_rtl_repeat_consistency_gate import build_gate


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_repeat_consistency_checks_status_cycles_and_hashes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        server = root / "server"
        for pass_name in ["golden", "rtl"]:
            case_dir = server / pass_name / "case_a"
            case_dir.mkdir(parents=True)
            (case_dir / "actual_joint_results.csv").write_text("1,2,3\n", encoding="utf-8")
        logs = server / "logs"
        logs.mkdir(parents=True)
        for pass_name in ["golden", "rtl"]:
            (logs / f"case_a_{pass_name}.log").write_text(
                "[TB] Done interrupt after 133 cycles at time 10\n"
                "[TB] Done interrupt after 133 cycles at time 20\n",
                encoding="utf-8",
            )
        write_csv(
            server / "results" / "value_repeat_status.csv",
            [
                {"case_id": "case_a", "pass_name": "golden", "rc": "0", "timeout": "no", "log": "value_repeat/logs/case_a_golden.log"},
                {"case_id": "case_a", "pass_name": "rtl", "rc": "0", "timeout": "no", "log": "value_repeat/logs/case_a_rtl.log"},
            ],
        )

        out_dir = root / "out"
        build_gate(server, out_dir)

        summary = read_csv(out_dir / "rtl_repeat_consistency_summary.csv")[0]
        assert summary["execution_clean_cases"] == "1"
        assert summary["timing_repeat_pass_cases"] == "1"
        assert summary["output_hash_pass_cases"] == "1"
        assert summary["direct_paper_ready_cases"] == "0"


if __name__ == "__main__":
    test_repeat_consistency_checks_status_cycles_and_hashes()
    print("RTL repeat consistency gate smoke test passed")
