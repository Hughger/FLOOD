#!/usr/bin/env python3
"""Smoke tests for independent golden feasibility auditing."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from build_independent_golden_feasibility import build_feasibility


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_repeatability_without_independent_golden_is_blocked_from_direct_paper_data() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tb = root / "testbench.v"
        make_hex = root / "make_simple_hex.py"
        projection = root / "projection.csv"
        repeat_gate = root / "repeat_gate.csv"
        consistency = root / "consistency.csv"
        out_dir = root / "out"

        write_text(
            tb,
            """
            $readmemh("weights_ping.hex", u_wping.mem);
            $readmemh("features.hex", feat_mem_global);
            task drive_feature_from_files;
            endtask
            task print_output_results;
              force oping_raddr = addr;
              temp_data = oping_rdata[col*16 +: 16];
            endtask
            task print_joint_results;
              force joint_raddr = addr;
            endtask
            planeWorkMode = 3;
            """,
        )
        write_text(
            make_hex,
            """
            Path("weights_ping.hex").write_text("x")
            Path("features.hex").write_text("x")
            feature_lines = args.group_num * args.res_rows
            """,
        )
        write_csv(
            projection,
            [
                {
                    "workload_id": "calib_09",
                    "projection_source": "p1_clean_progress",
                    "projected_total_cycles": "109200",
                    "direct_paper_ready": "no",
                }
            ],
        )
        write_csv(
            repeat_gate,
            [
                {
                    "repeat_value_gate_status": "pass",
                    "passed_cases": "4",
                    "total_compared_values": "4608",
                    "direct_paper_ready_cases": "0",
                }
            ],
        )
        write_csv(
            consistency,
            [
                {
                    "repeat_consistency_status": "pass",
                    "execution_clean_cases": "4",
                    "timing_repeat_pass_cases": "4",
                    "output_hash_pass_cases": "4",
                    "direct_paper_ready_cases": "0",
                }
            ],
        )

        build_feasibility(tb, make_hex, projection, repeat_gate, consistency, out_dir)

        summary = read_csv(out_dir / "independent_golden_feasibility_summary.csv")[0]
        assert summary["feasibility_status"] == "blocked_until_semantics_are_implemented"
        assert summary["repeatability_evidence_status"] == "pass"
        assert summary["direct_paper_ready_rows"] == "0"
        assert "python_independent_golden" in summary["main_blocker"]

        checks = {row["check"]: row for row in read_csv(out_dir / "independent_golden_feasibility_checks.csv")}
        assert checks["feature_hex_multi_resolution_column_packing"]["status"] == "missing"
        assert "RES_COL_TOTAL" in checks["feature_hex_multi_resolution_column_packing"]["paper_policy"]


if __name__ == "__main__":
    test_repeatability_without_independent_golden_is_blocked_from_direct_paper_data()
    print("Independent golden feasibility smoke test passed")
