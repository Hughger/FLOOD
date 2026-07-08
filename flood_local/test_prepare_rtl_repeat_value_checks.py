#!/usr/bin/env python3
"""Smoke tests for preparing RTL repeat value-check manifests."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from prepare_rtl_repeat_value_checks import prepare_checks


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_prepare_checks_concatenates_matching_golden_and_rtl_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        server = root / "server"
        (server / "golden" / "case_a").mkdir(parents=True)
        (server / "rtl" / "case_a").mkdir(parents=True)
        (server / "golden" / "case_a" / "actual_joint_results.csv").write_text("1,2\n", encoding="utf-8")
        (server / "golden" / "case_a" / "actual_output_results_r0.csv").write_text("3,4\n", encoding="utf-8")
        (server / "rtl" / "case_a" / "actual_joint_results.csv").write_text("1,2\n", encoding="utf-8")
        (server / "rtl" / "case_a" / "actual_output_results_r0.csv").write_text("3,4\n", encoding="utf-8")
        write_csv(
            server / "results" / "value_repeat_status.csv",
            [
                {"case_id": "case_a", "pass_name": "golden", "rc": "0", "timeout": "no"},
                {"case_id": "case_a", "pass_name": "rtl", "rc": "0", "timeout": "no"},
            ],
        )

        out_dir = root / "out"
        prepare_checks(server, out_dir)

        manifest = read_csv(out_dir / "value_repeat_manifest.csv")
        assert manifest[0]["workload_id"] == "case_a"
        assert Path(manifest[0]["golden_values"]).read_text(encoding="utf-8") == "1,2\n3,4\n"
        assert Path(manifest[0]["rtl_values"]).read_text(encoding="utf-8") == "1,2\n3,4\n"
        summary = read_csv(out_dir / "value_repeat_prepare_summary.csv")[0]
        assert summary["ready_cases"] == "1"


if __name__ == "__main__":
    test_prepare_checks_concatenates_matching_golden_and_rtl_files()
    print("RTL repeat value-check prepare smoke test passed")
