#!/usr/bin/env python3
"""Smoke tests for P1-priority RTL calibrated projection."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from build_rtl_calibrated_projection_v2 import build_projection


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_projection_prefers_clean_p1_over_p0_and_falls_back_when_p1_has_x() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan = root / "plan.csv"
        p0 = root / "p0.csv"
        p1 = root / "p1.csv"
        write_csv(
            plan,
            [
                {"next_case_id": "case_a_safe_tile", "source_case_id": "case_a", "full_layer_tile_count_estimate": "10"},
                {"next_case_id": "case_a_longer_partial", "source_case_id": "case_a", "full_layer_tile_count_estimate": "10"},
                {"next_case_id": "case_b_safe_tile", "source_case_id": "case_b", "full_layer_tile_count_estimate": "20"},
                {"next_case_id": "case_b_longer_partial", "source_case_id": "case_b", "full_layer_tile_count_estimate": "20"},
            ],
        )
        write_csv(
            p0,
            [
                {"next_case_id": "case_a_safe_tile", "source_case_id": "case_a", "run_count": "4", "total_cycles": "400", "expansion_status": "rtl_expansion_complete_clean", "ready_for_calibration": "yes"},
                {"next_case_id": "case_b_safe_tile", "source_case_id": "case_b", "run_count": "4", "total_cycles": "400", "expansion_status": "rtl_expansion_complete_clean", "ready_for_calibration": "yes"},
            ],
        )
        write_csv(
            p1,
            [
                {"next_case_id": "case_a_longer_partial", "source_case_id": "case_a", "run_count": "2", "total_cycles": "1000", "expansion_status": "rtl_expansion_partial_clean", "ready_for_calibration": "yes", "x_count": "0"},
                {"next_case_id": "case_b_longer_partial", "source_case_id": "case_b", "run_count": "2", "total_cycles": "1000", "expansion_status": "rtl_expansion_x_or_error", "ready_for_calibration": "no", "x_count": "5"},
            ],
        )

        out_dir = root / "out"
        build_projection(p0, p1, plan, out_dir)

        rows = read_csv(out_dir / "rtl_calibrated_projection_v2.csv")
        by_source = {row["source_case_id"]: row for row in rows}
        assert by_source["case_a"]["selected_priority"] == "P1"
        assert by_source["case_a"]["projected_mac_cycles"] == "5000"
        assert by_source["case_b"]["selected_priority"] == "P0"
        assert by_source["case_b"]["projected_mac_cycles"] == "2000"

        summary = read_csv(out_dir / "rtl_calibrated_projection_v2_summary.csv")[0]
        assert summary["p1_selected_rows"] == "1"
        assert summary["p0_fallback_rows"] == "1"
        assert summary["direct_paper_ready_rows"] == "0"


if __name__ == "__main__":
    test_projection_prefers_clean_p1_over_p0_and_falls_back_when_p1_has_x()
    print("RTL calibrated projection v2 smoke test passed")
