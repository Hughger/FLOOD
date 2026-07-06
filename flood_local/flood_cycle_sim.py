#!/usr/bin/env python3
"""Cycle-interval simulator for the current Base FLOOD MAC datapath.

This is the first executable simulator layer above the RTL calibration data.
It emits exact cycle intervals for each modeled MAC-machine run, rather than
only a single fitted total-cycle number.  The model is intentionally scoped:

- supported operators: GEMM and Conv mapped to the current Base FLOOD MAC path
- supported kernels: GEMM/k=1 and Conv k=1/k=3
- frequency: 330 MHz, matching the current 28nm FLOOD assumption
- confidence labels are emitted per row so projection-only rows are not mixed
  with direct RTL-clean evidence

The interval trace is compressed: one row can represent many identical cycles.
For a cycle-by-cycle dump, pass --cycle-trace-cap with a nonzero cap.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FREQ_MHZ = 330.0
TILE_ROWS = 16
REDUCTION_BLOCK = 32
OUTPUT_BLOCK = 32
DATA_WIDTH_BYTES = 1
DMA_DATA_BYTES = 8
DMA_DEFAULT_MAXBURST = 7
DMA_FSM_OVERHEAD_CYCLES = 4
CPU_CONFIG_WRITE_CYCLES = 1
MAC_CONFIG_WRITES = 3

DIRECT_CLEAN_WORKLOAD_IDS = {
    "trace_gemm_001",
    "trace_gemm_005",
    "trace_gemm_002",
    "trace_conv_013",
    "trace_gemm_014",
    "trace_gemm_015",
}

DIRECT_BLOCKED_WORKLOAD_IDS = {
    "attn_score_1024_64_1024",
    "trace_conv_018",
    "trace_gemm_007",
    "trace_gemm_008",
    "trace_gemm_016",
}


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def fnum(value: Any) -> float:
    if value in ("", None, "NA", "MISSING"):
        return 0.0
    return float(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_numeric_values(path: Path) -> list[float]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    values: list[float] = []
    for token in re.findall(r"[-+]?(?:0x[0-9a-fA-F]+|\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", text):
        try:
            values.append(float(int(token, 16)) if token.lower().startswith(("0x", "+0x", "-0x")) else float(token))
        except ValueError:
            continue
    return values


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@dataclass(frozen=True)
class Shape:
    m: int
    reduction: int
    n: int
    kernel: int
    workmode: str


@dataclass(frozen=True)
class SystemEvent:
    workload_id: str
    phase: str
    start_cycle: int
    duration_cycles: int
    end_cycle_exclusive: int
    bytes_moved: int
    rule: str


@dataclass(frozen=True)
class RunEvent:
    workload_id: str
    spatial_idx: int
    cin_idx: int
    phase: str
    start_cycle: int
    duration_cycles: int
    end_cycle_exclusive: int
    rule: str


@dataclass(frozen=True)
class SimParams:
    k: int
    cout: int
    cin_idx_total: int
    spatial_points: int
    workload_id: str


def parse_shape(operator: str, shape_args: str) -> Shape:
    dims = [int(x) for x in str(shape_args).split()]
    if operator == "gemm":
        if len(dims) != 3:
            raise ValueError(f"gemm shape must be M K N, got: {shape_args}")
        m, reduction, n = dims
        return Shape(m=m, reduction=reduction, n=n, kernel=1, workmode="gemm")
    if operator == "conv":
        if len(dims) != 8:
            raise ValueError(f"conv shape must be B H W IC OC K S P, got: {shape_args}")
        b, h, w, ic, oc, kernel, stride, pad = dims
        oh = (h + 2 * pad - kernel) // stride + 1
        ow = (w + 2 * pad - kernel) // stride + 1
        workmode = "pointwise_conv" if kernel == 1 else "spatial_conv"
        return Shape(m=b * oh * ow, reduction=ic * kernel * kernel, n=oc, kernel=kernel, workmode=workmode)
    raise ValueError(f"unsupported operator: {operator}")


def row_id(row: dict[str, str], index: int) -> str:
    return row.get("id") or row.get("workload") or f"row_{index:04d}"


def baseline_cycles(row: dict[str, str]) -> float:
    return fnum(row.get("pytorchsim_cycles") or row.get("total_cycles") or row.get("baseline_cycles"))


def shape_bytes(shape: Shape) -> dict[str, int]:
    weight = shape.reduction * shape.n * DATA_WIDTH_BYTES
    activation = shape.m * shape.reduction * DATA_WIDTH_BYTES
    output = shape.m * shape.n * DATA_WIDTH_BYTES
    return {"activation_bytes": activation, "weight_bytes": weight, "output_bytes": output}


def dma_cycles(num_bytes: int, maxburst: int = DMA_DEFAULT_MAXBURST) -> int:
    if num_bytes <= 0:
        return 0
    beats = ceil_div(num_bytes, DMA_DATA_BYTES)
    bursts = ceil_div(beats, max(1, maxburst))
    # One ideal beat per data beat plus request/response bookkeeping per burst.
    return DMA_FSM_OVERHEAD_CYCLES + beats + 2 * bursts


def config_cycles(write_count: int = MAC_CONFIG_WRITES) -> int:
    return max(0, write_count) * CPU_CONFIG_WRITE_CYCLES


def shape_to_params(workload_id: str, shape: Shape) -> SimParams:
    return SimParams(
        workload_id=workload_id,
        k=shape.kernel,
        cout=max(1, ceil_div(shape.n, OUTPUT_BLOCK)),
        cin_idx_total=max(1, ceil_div(shape.reduction, REDUCTION_BLOCK)),
        spatial_points=max(1, ceil_div(shape.m, TILE_ROWS)),
    )


def confidence_status(workload_id: str, k: int, cin: int, cout: int, spatial_points: int) -> tuple[str, str]:
    if workload_id in DIRECT_CLEAN_WORKLOAD_IDS:
        return "B_direct_rtl_clean_workload_row", "exact workload row has direct RTL-clean evidence"
    if workload_id in DIRECT_BLOCKED_WORKLOAD_IDS:
        return "D_direct_rtl_blocked", "direct RTL attempt observed invalid X/zero-cycle behavior"
    if k == 1 and cin >= 3 and spatial_points >= 16:
        return "D_observed_multicin_spatial_x_boundary", "known multi-Cin spatial boundary; do not use as clean paper data"
    if k == 1 and cin >= 2 and spatial_points >= 64:
        return "D_observed_large_spatial_x_boundary", "known large-spatial boundary; do not use as clean paper data"
    if k == 1 and cin >= 2 and spatial_points >= 2 and cout >= 29:
        return "D_observed_high_cout_multicin_boundary", "known high-Cout multi-Cin boundary"
    if k == 1 and spatial_points <= 16:
        return "C_projection_small_extent_not_directly_run", "cycle intervals use calibrated rules but this exact row was not RTL-run"
    if k == 3 and spatial_points <= 16 and cin <= 3:
        return "C_projection_k3_not_directly_run", "k3 rule supported by calibration but this exact row was not RTL-run"
    if k == 3:
        return "C_projection_large_k3_extent_unvalidated", "large k3 extent exceeds direct RTL-clean holdout range"
    return "C_projection_large_spatial_extent_unvalidated", "large spatial extent requires more direct RTL validation"


def simulate_params(params: SimParams) -> tuple[list[RunEvent], dict[str, Any]]:
    workload_id = params.workload_id
    spatial_points = params.spatial_points
    cin_idx_total = params.cin_idx_total
    cout = params.cout
    k = params.k

    if k not in {1, 3}:
        return [], {
            "sim_status": "unsupported_kernel",
            "sim_note": "current simulator supports k=1 and k=3 only",
            "k": k,
            "cout": cout,
            "cin_idx_total": cin_idx_total,
            "spatial_points": spatial_points,
        }

    events: list[RunEvent] = []
    cursor = 0
    for spatial_idx in range(spatial_points):
        if k == 1 and cin_idx_total == 1:
            duration = int(56 + 19 * max(0, cout - 2)) if spatial_idx == 0 else 56
            events.append(
                RunEvent(
                    workload_id=workload_id,
                    spatial_idx=spatial_idx,
                    cin_idx=0,
                    phase="single_cin_compute_store",
                    start_cycle=cursor,
                    duration_cycles=duration,
                    end_cycle_exclusive=cursor + duration,
                    rule="k1_group16_spatial_reuse_v8",
                )
            )
            cursor += duration
            continue

        if k == 1:
            for cin_idx in range(cin_idx_total):
                if spatial_idx == 0 and cin_idx == 0:
                    duration = int(19 * cout + 15)
                    phase = "first_spatial_first_cin_startup"
                elif cin_idx == cin_idx_total - 1:
                    duration = 56
                    phase = "final_cin_output_store"
                else:
                    duration = 53
                    phase = "middle_cin_accumulate"
                events.append(
                    RunEvent(
                        workload_id=workload_id,
                        spatial_idx=spatial_idx,
                        cin_idx=cin_idx,
                        phase=phase,
                        start_cycle=cursor,
                        duration_cycles=duration,
                        end_cycle_exclusive=cursor + duration,
                        rule="k1_group16_spatial_reuse_v8",
                    )
                )
                cursor += duration
            continue

        for cin_idx in range(cin_idx_total):
            final = cin_idx == cin_idx_total - 1
            duration = int(147 * cout + (38 if final else 35))
            events.append(
                RunEvent(
                    workload_id=workload_id,
                    spatial_idx=spatial_idx,
                    cin_idx=cin_idx,
                    phase="k3_final_cin_output_store" if final else "k3_nonfinal_cin_accumulate",
                    start_cycle=cursor,
                    duration_cycles=duration,
                    end_cycle_exclusive=cursor + duration,
                    rule="k3_group16_v7",
                )
            )
            cursor += duration

    confidence, note = confidence_status(workload_id, k, cin_idx_total, cout, spatial_points)
    return events, {
        "sim_status": "ok",
        "k": k,
        "cout": cout,
        "cin_idx_total": cin_idx_total,
        "spatial_points": spatial_points,
        "total_cycles": cursor,
        "latency_us_330mhz": round(cursor / FREQ_MHZ, 6),
        "confidence_grade": confidence,
        "confidence_note": note,
        "interval_count": len(events),
    }


def simulate_runs(workload_id: str, shape: Shape) -> tuple[list[RunEvent], dict[str, Any]]:
    return simulate_params(shape_to_params(workload_id, shape))


def simulate_system_events(workload_id: str, shape: Shape, mac_cycles: int) -> tuple[list[SystemEvent], dict[str, Any]]:
    sizes = shape_bytes(shape)
    phases = [
        (
            "cpu_config_writes",
            config_cycles(),
            0,
            "configBus writes from MacMachine_top/FSMDualMode; unvalidated fixed write latency",
        ),
        (
            "dma_activation_load",
            dma_cycles(sizes["activation_bytes"]),
            sizes["activation_bytes"],
            "dma_top 64-bit AXI read path; ideal ready/valid; unvalidated system projection",
        ),
        (
            "dma_weight_load",
            dma_cycles(sizes["weight_bytes"]),
            sizes["weight_bytes"],
            "dma_top 64-bit AXI read path; ideal ready/valid; unvalidated system projection",
        ),
        (
            "mac_datapath_run",
            mac_cycles,
            0,
            "cycle interval from Base FLOOD MAC datapath simulator",
        ),
        (
            "dma_output_store",
            dma_cycles(sizes["output_bytes"]),
            sizes["output_bytes"],
            "dma_top 64-bit AXI write path; ideal ready/valid; unvalidated system projection",
        ),
    ]
    events: list[SystemEvent] = []
    cursor = 0
    for phase, duration, bytes_moved, rule in phases:
        events.append(
            SystemEvent(
                workload_id=workload_id,
                phase=phase,
                start_cycle=cursor,
                duration_cycles=duration,
                end_cycle_exclusive=cursor + duration,
                bytes_moved=bytes_moved,
                rule=rule,
            )
        )
        cursor += duration
    return events, {
        **sizes,
        "config_cycles": phases[0][1],
        "activation_dma_cycles": phases[1][1],
        "weight_dma_cycles": phases[2][1],
        "output_dma_cycles": phases[4][1],
        "system_total_cycles": cursor,
        "system_latency_us_330mhz": round(cursor / FREQ_MHZ, 6),
        "system_model_status": "unvalidated_system_projection",
        "system_model_note": "Includes CPU config and DMA/SRAM transfer intervals from visible RTL widths, but not direct full-chip RTL-clean evidence.",
    }


def event_to_row(event: RunEvent) -> dict[str, Any]:
    return {
        "workload_id": event.workload_id,
        "spatial_idx": event.spatial_idx,
        "cin_idx": event.cin_idx,
        "phase": event.phase,
        "start_cycle": event.start_cycle,
        "duration_cycles": event.duration_cycles,
        "end_cycle_exclusive": event.end_cycle_exclusive,
        "rule": event.rule,
    }


def system_event_to_row(event: SystemEvent) -> dict[str, Any]:
    return {
        "workload_id": event.workload_id,
        "phase": event.phase,
        "start_cycle": event.start_cycle,
        "duration_cycles": event.duration_cycles,
        "end_cycle_exclusive": event.end_cycle_exclusive,
        "bytes_moved": event.bytes_moved,
        "rule": event.rule,
    }


def build_cycle_rows(events: list[RunEvent], cap: int) -> list[dict[str, Any]]:
    if cap <= 0:
        return []
    rows: list[dict[str, Any]] = []
    for event in events:
        for cycle in range(event.start_cycle, event.end_cycle_exclusive):
            if len(rows) >= cap:
                rows.append({"workload_id": event.workload_id, "cycle": "TRUNCATED", "phase": f"cap={cap}"})
                return rows
            rows.append(
                {
                    "workload_id": event.workload_id,
                    "cycle": cycle,
                    "spatial_idx": event.spatial_idx,
                    "cin_idx": event.cin_idx,
                    "phase": event.phase,
                    "rule": event.rule,
                }
            )
    return rows


def cycle_list(events: list[RunEvent]) -> str:
    return ";".join(str(event.duration_cycles) for event in events)


def build_rtl_validation_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_csv(path)
    details: list[dict[str, Any]] = []
    intervals: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        status = row.get("direct_status") or row.get("status") or ""
        if status != "rtl_clean_direct":
            continue
        params = SimParams(
            workload_id=row.get("workload_id") or row.get("case") or f"rtl_case_{index}",
            k=int(fnum(row.get("k"))),
            cout=int(fnum(row.get("cout"))),
            cin_idx_total=int(fnum(row.get("cin_idx_total"))),
            spatial_points=int(fnum(row.get("spatial_points"))),
        )
        events, sim = simulate_params(params)
        predicted_cycles = int(fnum(sim.get("total_cycles")))
        measured_cycles = int(fnum(row.get("direct_total_cycles") or row.get("total_cycles")))
        predicted_list = cycle_list(events)
        measured_list = row.get("cycle_list", "")
        pass_cycles = predicted_cycles == measured_cycles
        pass_list = predicted_list == measured_list
        details.append(
            {
                "case": row.get("case", ""),
                "workload_id": params.workload_id,
                "k": params.k,
                "cout": params.cout,
                "cin_idx_total": params.cin_idx_total,
                "spatial_points": params.spatial_points,
                "rtl_total_cycles": measured_cycles,
                "sim_total_cycles": predicted_cycles,
                "cycle_error": predicted_cycles - measured_cycles,
                "rtl_cycle_list": measured_list,
                "sim_cycle_list": predicted_list,
                "pass_cycles": pass_cycles,
                "pass_cycle_list": pass_list,
                "validation_status": "pass" if pass_cycles and pass_list else "fail",
            }
        )
        intervals.extend(event_to_row(event) for event in events)
    return details, intervals


def summarize_validation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(rows)
    passed = sum(1 for row in rows if row.get("validation_status") == "pass")
    max_abs_error = max((abs(int(row["cycle_error"])) for row in rows), default=0)
    return [
        {
            "rtl_clean_cases": total,
            "passed_cases": passed,
            "failed_cases": total - passed,
            "pass_rate_percent": round(passed / total * 100.0, 4) if total else 0.0,
            "max_abs_cycle_error": max_abs_error,
            "validation_scope": "direct RTL-clean MAC datapath cases only",
        }
    ]


def build_value_check(golden_path: Path | None, rtl_path: Path | None, rtol: float, atol: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if golden_path is None or rtl_path is None:
        return (
            [
                {
                    "value_check_status": "missing_evidence",
                    "golden_path": str(golden_path or ""),
                    "rtl_output_path": str(rtl_path or ""),
                    "num_values": 0,
                    "num_mismatches": "MISSING",
                    "max_abs_error": "MISSING",
                    "max_rel_error": "MISSING",
                    "note": "Provide both --golden-values and --rtl-values to validate output correctness.",
                }
            ],
            [],
        )
    if not golden_path.exists() or not rtl_path.exists():
        return (
            [
                {
                    "value_check_status": "missing_file",
                    "golden_path": str(golden_path),
                    "rtl_output_path": str(rtl_path),
                    "num_values": 0,
                    "num_mismatches": "MISSING",
                    "max_abs_error": "MISSING",
                    "max_rel_error": "MISSING",
                    "note": "At least one value file does not exist.",
                }
            ],
            [],
        )

    golden = read_numeric_values(golden_path)
    rtl = read_numeric_values(rtl_path)
    details: list[dict[str, Any]] = []
    mismatches = 0
    max_abs = 0.0
    max_rel = 0.0
    n = min(len(golden), len(rtl))
    for idx in range(n):
        g = golden[idx]
        r = rtl[idx]
        abs_err = abs(g - r)
        rel_err = abs_err / max(abs(g), 1e-12)
        max_abs = max(max_abs, abs_err)
        max_rel = max(max_rel, rel_err)
        passed = math.isclose(g, r, rel_tol=rtol, abs_tol=atol)
        if not passed:
            mismatches += 1
            if len(details) < 100:
                details.append(
                    {
                        "index": idx,
                        "golden": g,
                        "rtl": r,
                        "abs_error": abs_err,
                        "rel_error": rel_err,
                        "status": "mismatch",
                    }
                )
    length_mismatch = len(golden) != len(rtl)
    if length_mismatch:
        mismatches += abs(len(golden) - len(rtl))
    status = "pass" if mismatches == 0 else "fail"
    return (
        [
            {
                "value_check_status": status,
                "golden_path": str(golden_path),
                "rtl_output_path": str(rtl_path),
                "golden_values": len(golden),
                "rtl_values": len(rtl),
                "compared_values": n,
                "length_mismatch": length_mismatch,
                "num_mismatches": mismatches,
                "max_abs_error": max_abs,
                "max_rel_error": max_rel,
                "rtol": rtol,
                "atol": atol,
                "note": "Numeric token comparison; file format is not semantically parsed.",
            }
        ],
        details,
    )


def write_readme(out_dir: Path, summary_rows: list[dict[str, Any]], cycle_trace_cap: int) -> None:
    grades: dict[str, int] = {}
    for row in summary_rows:
        grades[str(row.get("confidence_grade"))] = grades.get(str(row.get("confidence_grade")), 0) + 1
    lines = [
        "# FLOOD cycle simulator v1",
        "",
        "This package is generated by `flood_local/flood_cycle_sim.py`.",
        "",
        "## What this is",
        "",
        "It is a cycle-interval simulator for the current Base FLOOD MAC datapath.",
        "Each interval row has an exact start cycle, duration, and end cycle.",
        "",
        "## What this is not",
        "",
        "It is not yet a full-chip RTL replacement: DMA, CPU control software, SRAM contents, and output-value checking are not fully simulated here.",
        "",
        "## Outputs",
        "",
        "- `workload_summary.csv`: one row per workload, including FLOOD cycles, latency, speedup, and confidence grade.",
        "- `cycle_intervals.csv`: compressed cycle-level state intervals for each workload.",
        "- `system_intervals.csv`: optional CPU config + DMA + MAC top-level intervals when `--include-system` is enabled.",
        "- `value_check_summary.csv`: output-value correctness status, emitted as missing_evidence unless golden and RTL value files are provided.",
        "- `cycle_trace.csv`: optional per-cycle trace, emitted only when `--cycle-trace-cap` is nonzero.",
        "",
        "## Confidence summary",
        "",
    ]
    for grade, count in sorted(grades.items()):
        lines.append(f"- {grade}: {count} rows")
    lines.extend(
        [
            "",
            f"cycle_trace_cap: {cycle_trace_cap}",
            "frequency_mhz: 330",
            "process: 28nm",
            "",
        ]
    )
    out_dir.joinpath("README.md").write_text("\n".join(lines), encoding="utf-8")


def write_validation_readme(out_dir: Path, summary: list[dict[str, Any]]) -> None:
    row = summary[0] if summary else {}
    lines = [
        "# FLOOD cycle simulator RTL validation",
        "",
        "This report compares simulator cycle intervals with direct RTL-clean cases.",
        "",
        "## Result",
        "",
        f"- rtl_clean_cases: {row.get('rtl_clean_cases', 0)}",
        f"- passed_cases: {row.get('passed_cases', 0)}",
        f"- failed_cases: {row.get('failed_cases', 0)}",
        f"- pass_rate_percent: {row.get('pass_rate_percent', 0)}",
        f"- max_abs_cycle_error: {row.get('max_abs_cycle_error', 0)}",
        "",
        "## Scope",
        "",
        "This validates the modeled MAC-machine run timing against direct RTL-clean evidence only.",
        "It does not validate DMA, CPU software control, SRAM data correctness, softmax, sparsity, zero-skip, or large blocked-X workload cases.",
        "",
    ]
    out_dir.joinpath("README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="", help="CSV with operator and shape_args columns.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--cycle-trace-cap", type=int, default=0)
    parser.add_argument("--rtl-validation", default="", help="Optional direct RTL-clean validation CSV.")
    parser.add_argument("--include-system", action="store_true", help="Emit unvalidated CPU config + DMA/SRAM system intervals.")
    parser.add_argument("--golden-values", default="", help="Optional golden numeric output file for value checking.")
    parser.add_argument("--rtl-values", default="", help="Optional RTL numeric output file for value checking.")
    parser.add_argument("--value-rtol", type=float, default=0.0)
    parser.add_argument("--value-atol", type=float, default=0.0)
    parser.add_argument("--value-check-only", action="store_true", help="Only run output-value checker.")
    args = parser.parse_args()

    if args.value_check_only:
        out_dir = Path(args.out_dir)
        value_summary, value_details = build_value_check(
            Path(args.golden_values) if args.golden_values else None,
            Path(args.rtl_values) if args.rtl_values else None,
            args.value_rtol,
            args.value_atol,
        )
        write_csv(out_dir / "value_check_summary.csv", value_summary)
        if value_details:
            write_csv(out_dir / "value_check_details.csv", value_details)
        print(f"wrote FLOOD value check to {out_dir}")
        return

    if args.rtl_validation:
        out_dir = Path(args.out_dir)
        details, intervals = build_rtl_validation_rows(Path(args.rtl_validation))
        summary = summarize_validation(details)
        write_csv(out_dir / "rtl_validation_details.csv", details)
        write_csv(out_dir / "rtl_validation_summary.csv", summary)
        write_csv(out_dir / "rtl_validation_intervals.csv", intervals)
        write_validation_readme(out_dir, summary)
        print(f"wrote FLOOD cycle simulator RTL validation to {out_dir}")
        return

    if not args.input:
        raise SystemExit("--input is required unless --rtl-validation is used")

    rows = read_csv(Path(args.input))
    out_dir = Path(args.out_dir)
    summary: list[dict[str, Any]] = []
    interval_rows: list[dict[str, Any]] = []
    system_interval_rows: list[dict[str, Any]] = []
    cycle_rows: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        wid = row_id(row, index)
        op = row.get("operator", "").lower()
        base = baseline_cycles(row)
        out: dict[str, Any] = {
            "id": wid,
            "source_stage": row.get("stage", ""),
            "operator": op,
            "shape_args": row.get("shape_args", ""),
            "pytorchsim_cycles": base if base else "",
        }
        try:
            shape = parse_shape(op, row.get("shape_args", ""))
            events, sim = simulate_runs(wid, shape)
            out.update(sim)
            flood_cycles = fnum(out.get("total_cycles"))
            out["mac_total_cycles"] = int(flood_cycles) if flood_cycles else ""
            out["speedup_vs_pytorchsim_cycles"] = round(base / flood_cycles, 6) if base and flood_cycles else ""
            out["model_scope"] = "Base FLOOD MAC path; no softmax/sparsity/zero-skip innovation modeled"
            interval_rows.extend(event_to_row(event) for event in events)
            if args.include_system:
                system_events, system = simulate_system_events(wid, shape, int(flood_cycles))
                out.update(system)
                system_cycles = fnum(out.get("system_total_cycles"))
                out["system_speedup_vs_pytorchsim_cycles"] = round(base / system_cycles, 6) if base and system_cycles else ""
                system_interval_rows.extend(system_event_to_row(event) for event in system_events)
            cycle_rows.extend(build_cycle_rows(events, args.cycle_trace_cap - len(cycle_rows)) if args.cycle_trace_cap else [])
        except Exception as exc:  # keep batch runs inspectable
            out.update({"sim_status": "error", "error": str(exc), "confidence_grade": "D_error"})
        summary.append(out)

    write_csv(out_dir / "workload_summary.csv", summary)
    write_csv(out_dir / "cycle_intervals.csv", interval_rows)
    value_summary, value_details = build_value_check(
        Path(args.golden_values) if args.golden_values else None,
        Path(args.rtl_values) if args.rtl_values else None,
        args.value_rtol,
        args.value_atol,
    )
    write_csv(out_dir / "value_check_summary.csv", value_summary)
    if value_details:
        write_csv(out_dir / "value_check_details.csv", value_details)
    if args.include_system:
        write_csv(out_dir / "system_intervals.csv", system_interval_rows)
    if args.cycle_trace_cap:
        write_csv(out_dir / "cycle_trace.csv", cycle_rows)
    write_readme(out_dir, summary, args.cycle_trace_cap)
    print(f"wrote FLOOD cycle simulator output to {out_dir}")


if __name__ == "__main__":
    main()
