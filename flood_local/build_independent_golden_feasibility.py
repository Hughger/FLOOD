#!/usr/bin/env python3
"""Audit whether current RTL evidence has an independent software golden path."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def first_row(path: Path) -> dict[str, str]:
    rows = read_rows(path)
    return rows[0] if rows else {}


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["status"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "0") or 0))
    except ValueError:
        return 0


def has_all(text: str, needles: list[str]) -> bool:
    return all(needle in text for needle in needles)


def feature_generator_supports_multi_res_cols(text: str) -> bool:
    """Detect whether features.hex explicitly packs more than one resolution column per row."""
    if not text:
        return False
    multi_col_markers = [
        "range(args.res_cols)",
        "range(args.res_cols_total)",
        "args.res_cols *",
        "* args.res_cols",
        "RES_COL_TOTAL",
        "line_multi256",
    ]
    width_markers = ["FEAT_DATAW", "256 * args.res_cols", "args.res_cols * 256", "feature_row_bytes", "line_multi256"]
    return any(marker in text for marker in multi_col_markers) and any(marker in text for marker in width_markers)


def build_feasibility(
    testbench: Path,
    make_hex: Path,
    projection_csv: Path,
    repeat_gate_summary_csv: Path,
    repeat_consistency_summary_csv: Path,
    out_dir: Path,
    mapping_helper: Path | None = None,
) -> None:
    if mapping_helper is None:
        mapping_helper = Path(__file__).with_name("rtl_hex_mapping.py")
    tb_text = read_text(testbench)
    hex_text = read_text(make_hex)
    projections = read_rows(projection_csv)
    repeat_gate = first_row(repeat_gate_summary_csv)
    consistency = first_row(repeat_consistency_summary_csv)

    checks = [
        {
            "check": "rtl_testbench_available",
            "status": "pass" if tb_text else "missing",
            "evidence": str(testbench),
            "paper_policy": "required_for_reproduction",
        },
        {
            "check": "input_hex_generator_available",
            "status": "pass" if has_all(hex_text, ["weights_ping.hex", "features.hex"]) else "missing",
            "evidence": str(make_hex),
            "paper_policy": "required_for_independent_golden",
        },
        {
            "check": "rtl_reads_weight_and_feature_hex",
            "status": "pass" if has_all(tb_text, ['weights_ping.hex', 'features.hex', '$readmemh']) else "missing",
            "evidence": "$readmemh weights/features",
            "paper_policy": "required_for_reproduction",
        },
        {
            "check": "feature_hex_multi_resolution_column_packing",
            "status": "pass" if feature_generator_supports_multi_res_cols(hex_text) else "missing",
            "evidence": "features.hex must pack RES_COL_TOTAL * FEAT_DATAW bits per memory row when RES_COL_TOTAL>1.",
            "paper_policy": "RES_COL_TOTAL_greater_than_1_blocks_independent_golden_until_packing_is_explicit",
        },
        {
            "check": "feature_mapping_logic_visible",
            "status": "pass" if has_all(tb_text, ["drive_feature_from_files", "addr_in_hex", "feature_data"]) else "missing",
            "evidence": "drive_feature_from_files",
            "paper_policy": "required_for_independent_golden",
        },
        {
            "check": "python_feature_hex_mapping_helper_available",
            "status": "pass" if mapping_helper.exists() else "missing",
            "evidence": str(mapping_helper),
            "paper_policy": "input_mapping_foundation_for_independent_golden",
        },
        {
            "check": "output_sram_dump_logic_visible",
            "status": "pass" if has_all(tb_text, ["print_output_results", "oping_rdata", "signed_data"]) else "missing",
            "evidence": "print_output_results",
            "paper_policy": "required_for_independent_golden",
        },
        {
            "check": "joint_sram_dump_logic_visible",
            "status": "pass" if has_all(tb_text, ["print_joint_results", "joint_rdata", "signed_data"]) else "missing",
            "evidence": "print_joint_results",
            "paper_policy": "required_for_independent_golden",
        },
        {
            "check": "stateful_plane_work_modes_visible",
            "status": "pass" if "planeWorkMode" in tb_text else "missing",
            "evidence": "planeWorkMode controls cross-tile/cross-plane accumulation",
            "paper_policy": "must_be_modelled_before_direct_paper_use",
        },
        {
            "check": "rtl_repeatability_value_evidence_present",
            "status": "pass"
            if repeat_gate.get("repeat_value_gate_status") == "pass" and as_int(repeat_gate, "passed_cases") > 0
            else "missing",
            "evidence": (
                f"passed_cases={repeat_gate.get('passed_cases','0')}, "
                f"compared_values={repeat_gate.get('total_compared_values','0')}"
            ),
            "paper_policy": "repeatability_only_not_independent_golden",
        },
        {
            "check": "rtl_repeatability_hash_and_timing_present",
            "status": "pass"
            if consistency.get("repeat_consistency_status") == "pass"
            and as_int(consistency, "timing_repeat_pass_cases") > 0
            and as_int(consistency, "output_hash_pass_cases") > 0
            else "missing",
            "evidence": (
                f"timing_repeat={consistency.get('timing_repeat_pass_cases','0')}, "
                f"hash_repeat={consistency.get('output_hash_pass_cases','0')}"
            ),
            "paper_policy": "repeatability_only_not_independent_golden",
        },
        {
            "check": "python_independent_golden_implemented",
            "status": "missing",
            "evidence": "No implemented Python reference for feature/weight packing, planeWorkMode accumulation, output SRAM and joint SRAM semantics.",
            "paper_policy": "blocks_direct_paper_value_correctness",
        },
    ]

    pass_checks = sum(1 for row in checks if row["status"] == "pass")
    direct_paper_ready_rows = sum(
        1
        for row in projections
        if row.get("direct_paper_ready", "").lower() == "yes"
        or row.get("ready_for_direct_paper_data", "").lower() == "yes"
    )
    repeatability_pass = (
        repeat_gate.get("repeat_value_gate_status") == "pass"
        and consistency.get("repeat_consistency_status") == "pass"
    )
    summary = [
        {
            "feasibility_status": "blocked_until_semantics_are_implemented",
            "checks": str(len(checks)),
            "pass_checks": str(pass_checks),
            "missing_checks": str(len(checks) - pass_checks),
            "repeatability_evidence_status": "pass" if repeatability_pass else "missing",
            "projected_rows": str(len(projections)),
            "direct_paper_ready_rows": str(direct_paper_ready_rows),
            "can_generate_student_batch_inputs": "yes",
            "can_claim_independent_value_correctness": "no",
            "main_blocker": "python_independent_golden_for_feature_weight_mapping_plane_work_mode_and_sram_dump_semantics",
        }
    ]

    write_csv(out_dir / "independent_golden_feasibility_checks.csv", checks)
    write_csv(out_dir / "independent_golden_feasibility_summary.csv", summary)
    readme = """# Independent Golden Feasibility Audit

This audit separates repeatability evidence from independent correctness
evidence. Current RTL repeat runs are useful because they show the same inputs
produce identical timing and output files across runs.

They are still not enough for direct paper value correctness. The missing piece
is an independent Python golden model that exactly reproduces:

- `features.hex` and `weights_ping.hex` packing.
- `drive_feature_from_files` address mapping.
- `planeWorkMode` stateful accumulation.
- Output SRAM and Joint SRAM dump semantics.

Until that model exists and passes value checks, calibrated RTL projections
remain review/calibration data, not final main-figure paper rows.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--testbench",
        default="results/flood_pytorchsim_backend_v1/rtl_calibration_src/src/test/verilog/testbench_r32c32t16.v",
    )
    parser.add_argument(
        "--make-hex",
        default="results/flood_pytorchsim_backend_v1/rtl_calibration_src/make_simple_hex.py",
    )
    parser.add_argument(
        "--projection-csv",
        default="results/flood_cycle_sim_v1/rtl_calibrated_projection_v2/rtl_calibrated_projection_v2.csv",
    )
    parser.add_argument(
        "--repeat-gate-summary",
        default="results/flood_cycle_sim_v1/rtl_value_repeat_gate/rtl_value_repeat_gate_summary.csv",
    )
    parser.add_argument(
        "--repeat-consistency-summary",
        default="results/flood_cycle_sim_v1/rtl_repeat_consistency_gate/rtl_repeat_consistency_summary.csv",
    )
    parser.add_argument("--mapping-helper", default="flood_local/rtl_hex_mapping.py")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/independent_golden_feasibility")
    args = parser.parse_args()
    build_feasibility(
        Path(args.testbench),
        Path(args.make_hex),
        Path(args.projection_csv),
        Path(args.repeat_gate_summary),
        Path(args.repeat_consistency_summary),
        Path(args.out_dir),
        Path(args.mapping_helper),
    )


if __name__ == "__main__":
    main()
