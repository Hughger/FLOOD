#!/usr/bin/env python3
"""Smoke tests for HPCA figure contract generation."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from build_hpca_figure_contract import build_contract


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_contract_blocks_main_claims_without_real_value_and_system_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "results" / "flood_cycle_sim_v1"
        legacy = Path(tmp) / "legacy"
        out = Path(tmp) / "out"
        write_csv(root / "postprocessor_scorecard" / "postprocessor_summary.csv", [
            {
                "main_figure_rows": "0",
                "non_pass_checks": "2",
                "primary_blocker": "real workload golden/RTL value outputs and full-chip calibration logs",
            }
        ])
        write_csv(root / "final_paper_gate_smoke" / "final_paper_data_summary.csv", [
            {"paper_rows": "2", "ready_for_main_figure": "0", "not_ready_for_main_figure": "2"}
        ])
        write_csv(root / "rtl_validation" / "rtl_validation_summary.csv", [
            {"rtl_clean_cases": "6", "passed_cases": "6", "failed_cases": "0"}
        ])
        write_csv(root / "value_check_batch_smoke" / "value_readiness_summary.csv", [
            {"main_value_ready_policy": "not_ready_for_main_figure"}
        ])
        write_csv(root / "system_calibration_batch_smoke" / "calibration_readiness_summary.csv", [
            {"paper_system_timing_policy": "not_ready_for_main_figure"}
        ])
        write_csv(legacy / "legacy_ppa.csv", [
            {"metric": "frequency_mhz", "value": "330", "data_source": "legacy_micro_reference"}
        ])

        backend = Path(tmp) / "backend"
        build_contract(root, legacy, out, backend)

        rows = read_csv(out / "hpca_figure_contract.csv")
        by_fig = {row["figure_id"]: row for row in rows}
        assert by_fig["Fig.3"]["status"] == "partial"
        assert by_fig["Fig.6"]["status"] == "missing"
        assert by_fig["Fig.8"]["status"] == "partial"

        summary = read_csv(out / "hpca_figure_contract_summary.csv")[0]
        assert summary["paper_ready_figures"] == "0"
        assert summary["goal_status"] == "not_ready_for_direct_paper_plotting"


if __name__ == "__main__":
    test_contract_blocks_main_claims_without_real_value_and_system_evidence()
    print("hpca figure contract smoke test passed")
