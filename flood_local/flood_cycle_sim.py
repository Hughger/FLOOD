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


@dataclass(frozen=True)
class SystemModel:
    name: str
    dma_data_bytes: int
    dma_maxburst: int
    dma_fsm_overhead_cycles: int
    dma_burst_overhead_cycles: int
    cpu_config_write_cycles: int
    mac_config_writes: int
    system_model_status: str
    system_model_note: str


DEFAULT_SYSTEM_MODEL = SystemModel(
    name="default_visible_rtl_interface_model",
    dma_data_bytes=DMA_DATA_BYTES,
    dma_maxburst=DMA_DEFAULT_MAXBURST,
    dma_fsm_overhead_cycles=DMA_FSM_OVERHEAD_CYCLES,
    dma_burst_overhead_cycles=2,
    cpu_config_write_cycles=CPU_CONFIG_WRITE_CYCLES,
    mac_config_writes=MAC_CONFIG_WRITES,
    system_model_status="unvalidated_system_projection",
    system_model_note="Includes CPU config and DMA/SRAM transfer intervals from visible RTL widths, but not direct full-chip RTL-clean evidence.",
)


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def fnum(value: Any) -> float:
    if value in ("", None, "NA", "MISSING"):
        return 0.0
    return float(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_system_model(path: Path | None) -> SystemModel:
    if path is None or not str(path):
        return DEFAULT_SYSTEM_MODEL
    rows = read_csv(path)
    values: dict[str, str] = {}
    for row in rows:
        key = row.get("parameter") or row.get("name")
        value = row.get("calibrated_value") or row.get("value") or row.get("current_value")
        if key and value not in ("", None, "NA", "MISSING"):
            values[key] = str(value)

    def get_int(key: str, default: int) -> int:
        return int(float(values.get(key, default)))

    return SystemModel(
        name=values.get("system_model_name", path.stem),
        dma_data_bytes=get_int("dma_data_bytes", DEFAULT_SYSTEM_MODEL.dma_data_bytes),
        dma_maxburst=get_int("dma_maxburst", DEFAULT_SYSTEM_MODEL.dma_maxburst),
        dma_fsm_overhead_cycles=get_int("dma_fsm_overhead_cycles", DEFAULT_SYSTEM_MODEL.dma_fsm_overhead_cycles),
        dma_burst_overhead_cycles=get_int("dma_burst_overhead_cycles", DEFAULT_SYSTEM_MODEL.dma_burst_overhead_cycles),
        cpu_config_write_cycles=get_int("cpu_config_write_cycles", DEFAULT_SYSTEM_MODEL.cpu_config_write_cycles),
        mac_config_writes=get_int("mac_config_writes", DEFAULT_SYSTEM_MODEL.mac_config_writes),
        system_model_status=values.get("system_model_status", "calibrated_or_user_supplied_system_model"),
        system_model_note=values.get("system_model_note", f"Loaded from {path}"),
    )


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


def write_hardware_profile(out_dir: Path, system_model: SystemModel = DEFAULT_SYSTEM_MODEL) -> None:
    rows = [
        {
            "parameter": "system_model_name",
            "value": system_model.name,
            "unit": "",
            "source_or_basis": "active system model for this run",
            "evidence_grade": system_model.system_model_status,
        },
        {
            "parameter": "process_node",
            "value": "28nm",
            "unit": "",
            "source_or_basis": "user-provided FLOOD ASIC assumption",
            "evidence_grade": "assumption_for_all_reported_latency",
        },
        {
            "parameter": "frequency",
            "value": FREQ_MHZ,
            "unit": "MHz",
            "source_or_basis": "user-provided FLOOD ASIC assumption",
            "evidence_grade": "assumption_for_all_reported_latency",
        },
        {
            "parameter": "tile_rows",
            "value": TILE_ROWS,
            "unit": "rows",
            "source_or_basis": "current Base FLOOD MAC datapath model",
            "evidence_grade": "calibrated_against_direct_rtl_clean_cases",
        },
        {
            "parameter": "reduction_block",
            "value": REDUCTION_BLOCK,
            "unit": "channels",
            "source_or_basis": "current Base FLOOD MAC datapath model",
            "evidence_grade": "calibrated_against_direct_rtl_clean_cases",
        },
        {
            "parameter": "output_block",
            "value": OUTPUT_BLOCK,
            "unit": "channels",
            "source_or_basis": "current Base FLOOD MAC datapath model",
            "evidence_grade": "calibrated_against_direct_rtl_clean_cases",
        },
        {
            "parameter": "data_width",
            "value": DATA_WIDTH_BYTES,
            "unit": "bytes",
            "source_or_basis": "current simulator assumes int8-equivalent traffic for base path",
            "evidence_grade": "model_assumption",
        },
        {
            "parameter": "dma_data_bytes",
            "value": system_model.dma_data_bytes,
            "unit": "bytes",
            "source_or_basis": "dma_top 64-bit AXI path",
            "evidence_grade": "rtl_interface_observed",
        },
        {
            "parameter": "dma_maxburst",
            "value": system_model.dma_maxburst,
            "unit": "beats",
            "source_or_basis": "active system model",
            "evidence_grade": system_model.system_model_status,
        },
        {
            "parameter": "dma_fsm_overhead_cycles",
            "value": system_model.dma_fsm_overhead_cycles,
            "unit": "cycles",
            "source_or_basis": "active system model",
            "evidence_grade": system_model.system_model_status,
        },
        {
            "parameter": "dma_burst_overhead_cycles",
            "value": system_model.dma_burst_overhead_cycles,
            "unit": "cycles/burst",
            "source_or_basis": "active system model",
            "evidence_grade": system_model.system_model_status,
        },
        {
            "parameter": "mac_config_writes",
            "value": system_model.mac_config_writes,
            "unit": "writes",
            "source_or_basis": "active system model",
            "evidence_grade": system_model.system_model_status,
        },
        {
            "parameter": "cpu_config_write_cycles",
            "value": system_model.cpu_config_write_cycles,
            "unit": "cycles/write",
            "source_or_basis": "active system model",
            "evidence_grade": system_model.system_model_status,
        },
    ]
    write_csv(out_dir / "hardware_profile.csv", rows)


def write_system_model_template(out_dir: Path, system_model: SystemModel = DEFAULT_SYSTEM_MODEL) -> None:
    rows = [
        {
            "parameter": "system_model_name",
            "current_value": system_model.name,
            "calibrated_value": "",
            "unit": "",
            "notes": "Optional name for the active system model.",
        },
        {
            "parameter": "dma_data_bytes",
            "current_value": system_model.dma_data_bytes,
            "calibrated_value": "",
            "unit": "bytes",
            "notes": "AXI/DMA data width. Keep 8 for 64-bit DMA unless RTL says otherwise.",
        },
        {
            "parameter": "dma_maxburst",
            "current_value": system_model.dma_maxburst,
            "calibrated_value": "",
            "unit": "beats",
            "notes": "Burst length used by dma_cycles = fsm_overhead + beats + burst_overhead*bursts.",
        },
        {
            "parameter": "dma_fsm_overhead_cycles",
            "current_value": system_model.dma_fsm_overhead_cycles,
            "calibrated_value": "",
            "unit": "cycles",
            "notes": "Fixed DMA setup/finish overhead per transfer.",
        },
        {
            "parameter": "dma_burst_overhead_cycles",
            "current_value": system_model.dma_burst_overhead_cycles,
            "calibrated_value": "",
            "unit": "cycles/burst",
            "notes": "Handshake/bookkeeping overhead per burst.",
        },
        {
            "parameter": "cpu_config_write_cycles",
            "current_value": system_model.cpu_config_write_cycles,
            "calibrated_value": "",
            "unit": "cycles/write",
            "notes": "CPU/configBus write latency.",
        },
        {
            "parameter": "mac_config_writes",
            "current_value": system_model.mac_config_writes,
            "calibrated_value": "",
            "unit": "writes",
            "notes": "Number of configuration writes before a MAC run.",
        },
        {
            "parameter": "system_model_status",
            "current_value": system_model.system_model_status,
            "calibrated_value": "",
            "unit": "",
            "notes": "Use full_chip_rtl_calibrated only after system_calibration_summary proves the claimed scope.",
        },
        {
            "parameter": "system_model_note",
            "current_value": system_model.system_model_note,
            "calibrated_value": "",
            "unit": "",
            "notes": "Short provenance note shown in output rows.",
        },
    ]
    write_csv(out_dir / "system_model_template.csv", rows)


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
    return row.get("id") or row.get("workload_id") or row.get("workload") or f"row_{index:04d}"


def baseline_cycles(row: dict[str, str]) -> float:
    return fnum(row.get("pytorchsim_cycles") or row.get("total_cycles") or row.get("baseline_cycles"))


def shape_bytes(shape: Shape) -> dict[str, int]:
    weight = shape.reduction * shape.n * DATA_WIDTH_BYTES
    activation = shape.m * shape.reduction * DATA_WIDTH_BYTES
    output = shape.m * shape.n * DATA_WIDTH_BYTES
    return {"activation_bytes": activation, "weight_bytes": weight, "output_bytes": output}


def dma_cycles(num_bytes: int, system_model: SystemModel = DEFAULT_SYSTEM_MODEL) -> int:
    if num_bytes <= 0:
        return 0
    beats = ceil_div(num_bytes, system_model.dma_data_bytes)
    bursts = ceil_div(beats, max(1, system_model.dma_maxburst))
    # One ideal beat per data beat plus request/response bookkeeping per burst.
    return system_model.dma_fsm_overhead_cycles + beats + system_model.dma_burst_overhead_cycles * bursts


def config_cycles(system_model: SystemModel = DEFAULT_SYSTEM_MODEL) -> int:
    return max(0, system_model.mac_config_writes) * system_model.cpu_config_write_cycles


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


def simulate_system_events(workload_id: str, shape: Shape, mac_cycles: int, system_model: SystemModel = DEFAULT_SYSTEM_MODEL) -> tuple[list[SystemEvent], dict[str, Any]]:
    sizes = shape_bytes(shape)
    phases = [
        (
            "cpu_config_writes",
            config_cycles(system_model),
            0,
            f"configBus writes from MacMachine_top/FSMDualMode; model={system_model.name}",
        ),
        (
            "dma_activation_load",
            dma_cycles(sizes["activation_bytes"], system_model),
            sizes["activation_bytes"],
            f"dma_top read path; model={system_model.name}",
        ),
        (
            "dma_weight_load",
            dma_cycles(sizes["weight_bytes"], system_model),
            sizes["weight_bytes"],
            f"dma_top read path; model={system_model.name}",
        ),
        (
            "mac_datapath_run",
            mac_cycles,
            0,
            "cycle interval from Base FLOOD MAC datapath simulator",
        ),
        (
            "dma_output_store",
            dma_cycles(sizes["output_bytes"], system_model),
            sizes["output_bytes"],
            f"dma_top write path; model={system_model.name}",
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
        "system_model_name": system_model.name,
        "system_model_status": system_model.system_model_status,
        "system_model_note": system_model.system_model_note,
    }


def system_prediction_for_row(row: dict[str, str], index: int, system_model: SystemModel = DEFAULT_SYSTEM_MODEL) -> dict[str, Any]:
    wid = row_id(row, index)
    op = row.get("operator", "").lower()
    shape = parse_shape(op, row.get("shape_args", ""))
    events, sim = simulate_runs(wid, shape)
    mac_cycles = int(fnum(sim.get("total_cycles")))
    _system_events, system = simulate_system_events(wid, shape, mac_cycles, system_model)
    return {
        "workload_id": wid,
        "operator": op,
        "shape_args": row.get("shape_args", ""),
        "predicted_config_cycles": system["config_cycles"],
        "predicted_activation_dma_cycles": system["activation_dma_cycles"],
        "predicted_weight_dma_cycles": system["weight_dma_cycles"],
        "predicted_mac_cycles": mac_cycles,
        "predicted_output_dma_cycles": system["output_dma_cycles"],
        "predicted_system_total_cycles": system["system_total_cycles"],
        "prediction_status": "ok",
        "confidence_grade": sim.get("confidence_grade", ""),
        "confidence_note": sim.get("confidence_note", ""),
    }


def measured_field(row: dict[str, str], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        if value not in ("", None, "NA", "MISSING"):
            return float(value)
    return None


def cycle_error_fields(predicted: float, measured: float | None, prefix: str) -> dict[str, Any]:
    if measured is None:
        return {
            f"measured_{prefix}_cycles": "",
            f"{prefix}_cycle_error": "",
            f"{prefix}_error_percent": "",
            f"{prefix}_calibration_status": "missing_measurement",
        }
    error = predicted - measured
    return {
        f"measured_{prefix}_cycles": measured,
        f"{prefix}_cycle_error": error,
        f"{prefix}_error_percent": round(error / measured * 100.0, 6) if measured else "",
        f"{prefix}_calibration_status": "pass" if error == 0 else "mismatch",
    }


def build_system_calibration_rows(path: Path, system_model: SystemModel = DEFAULT_SYSTEM_MODEL) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_csv(path)
    details: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        try:
            pred = system_prediction_for_row(row, index, system_model)
            measured_config = measured_field(row, "measured_config_cycles", "rtl_config_cycles", "config_cycles")
            measured_activation = measured_field(row, "measured_activation_dma_cycles", "rtl_activation_dma_cycles", "activation_dma_cycles")
            measured_weight = measured_field(row, "measured_weight_dma_cycles", "rtl_weight_dma_cycles", "weight_dma_cycles")
            measured_mac = measured_field(row, "measured_mac_cycles", "rtl_mac_cycles", "mac_cycles")
            measured_output = measured_field(row, "measured_output_dma_cycles", "rtl_output_dma_cycles", "output_dma_cycles")
            measured_total = measured_field(row, "measured_system_total_cycles", "rtl_system_total_cycles", "system_total_cycles", "total_cycles")
            out: dict[str, Any] = {
                "workload_id": pred["workload_id"],
                "operator": pred["operator"],
                "shape_args": pred["shape_args"],
                "rtl_status": row.get("rtl_status", ""),
                "notes": row.get("notes", ""),
                "confidence_grade": pred["confidence_grade"],
                "system_model_name": system_model.name,
                "system_model_status": system_model.system_model_status,
            }
            for prefix, predicted, measured in [
                ("config", pred["predicted_config_cycles"], measured_config),
                ("activation_dma", pred["predicted_activation_dma_cycles"], measured_activation),
                ("weight_dma", pred["predicted_weight_dma_cycles"], measured_weight),
                ("mac", pred["predicted_mac_cycles"], measured_mac),
                ("output_dma", pred["predicted_output_dma_cycles"], measured_output),
                ("system_total", pred["predicted_system_total_cycles"], measured_total),
            ]:
                out[f"predicted_{prefix}_cycles"] = predicted
                out.update(cycle_error_fields(float(predicted), measured, prefix))
            phase_statuses = [str(value) for key, value in out.items() if key.endswith("_calibration_status")]
            if all(status == "pass" for status in phase_statuses):
                out["system_calibration_status"] = "pass"
            elif any(status == "mismatch" for status in phase_statuses):
                out["system_calibration_status"] = "mismatch"
            else:
                out["system_calibration_status"] = "missing_measurement"
            details.append(out)
        except Exception as exc:
            details.append(
                {
                    "workload_id": row_id(row, index),
                    "operator": row.get("operator", ""),
                    "shape_args": row.get("shape_args", ""),
                    "system_calibration_status": "error",
                    "error": str(exc),
                }
            )

    measured = [
        row for row in details
        if row.get("system_calibration_status") in {"pass", "mismatch"}
    ]
    mismatches = [row for row in measured if row.get("system_calibration_status") == "mismatch"]
    max_abs_total_error = max((abs(float(row.get("system_total_cycle_error") or 0)) for row in measured), default=0.0)
    max_abs_total_error_percent = max((abs(float(row.get("system_total_error_percent") or 0)) for row in measured), default=0.0)
    summary = [
        {
            "rows": len(details),
            "measured_rows": len(measured),
            "pass_rows": len(measured) - len(mismatches),
            "mismatch_rows": len(mismatches),
            "missing_measurement_rows": sum(1 for row in details if row.get("system_calibration_status") == "missing_measurement"),
            "error_rows": sum(1 for row in details if row.get("system_calibration_status") == "error"),
            "max_abs_system_total_cycle_error": max_abs_total_error,
            "max_abs_system_total_error_percent": round(max_abs_total_error_percent, 6),
            "calibration_scope": "CPU config + DMA + MAC total phase comparison against full-chip RTL/testbench measurements when supplied",
            "paper_use_policy": "system main-table use requires measured_rows>0 and mismatch_rows=0 for the claimed scope",
        }
    ]
    return details, summary


def solve_two_param_least_squares(samples: list[tuple[float, float, float]]) -> tuple[float, float] | None:
    if not samples:
        return None
    # y = a + b*x, where y=(measured_dma_cycles - ideal_beats), x=bursts.
    n = float(len(samples))
    sum_x = sum(x for x, _beats, y in samples)
    sum_y = sum(y for _x, _beats, y in samples)
    sum_xx = sum(x * x for x, _beats, _y in samples)
    sum_xy = sum(x * y for x, _beats, y in samples)
    det = n * sum_xx - sum_x * sum_x
    if abs(det) < 1e-12:
        return (sum_y / n, 0.0)
    a = (sum_y * sum_xx - sum_x * sum_xy) / det
    b = (n * sum_xy - sum_x * sum_y) / det
    return a, b


def build_system_model_suggestion_rows(path: Path, system_model: SystemModel = DEFAULT_SYSTEM_MODEL) -> list[dict[str, Any]]:
    rows = read_csv(path)
    dma_samples: list[tuple[float, float, float]] = []
    config_per_write: list[float] = []
    used_rows = 0
    for index, row in enumerate(rows):
        try:
            op = row.get("operator", "").lower()
            shape = parse_shape(op, row.get("shape_args", ""))
            sizes = shape_bytes(shape)
            measured_config = measured_field(row, "measured_config_cycles", "rtl_config_cycles", "config_cycles")
            if measured_config is not None and system_model.mac_config_writes:
                config_per_write.append(measured_config / system_model.mac_config_writes)
            for phase, bytes_key, field_names in [
                ("activation_dma", "activation_bytes", ("measured_activation_dma_cycles", "rtl_activation_dma_cycles", "activation_dma_cycles")),
                ("weight_dma", "weight_bytes", ("measured_weight_dma_cycles", "rtl_weight_dma_cycles", "weight_dma_cycles")),
                ("output_dma", "output_bytes", ("measured_output_dma_cycles", "rtl_output_dma_cycles", "output_dma_cycles")),
            ]:
                measured = measured_field(row, *field_names)
                if measured is None:
                    continue
                beats = ceil_div(sizes[bytes_key], system_model.dma_data_bytes)
                bursts = ceil_div(beats, max(1, system_model.dma_maxburst))
                dma_samples.append((float(bursts), float(beats), float(measured - beats)))
                used_rows += 1
        except Exception:
            continue

    dma_fit = solve_two_param_least_squares(dma_samples)
    suggested_fsm = system_model.dma_fsm_overhead_cycles
    suggested_burst = system_model.dma_burst_overhead_cycles
    if dma_fit is not None:
        suggested_fsm = max(0, int(round(dma_fit[0])))
        suggested_burst = max(0, int(round(dma_fit[1])))
    suggested_config = system_model.cpu_config_write_cycles
    if config_per_write:
        suggested_config = max(0, int(round(sum(config_per_write) / len(config_per_write))))

    fit_status = "insufficient_measurements"
    if dma_samples or config_per_write:
        fit_status = "suggestion_from_measured_phase_cycles"

    return [
        {
            "parameter": "system_model_name",
            "current_value": system_model.name,
            "suggested_value": f"{system_model.name}_fitted",
            "unit": "",
            "fit_status": fit_status,
            "fit_basis": "phase-level measured cycles, not system-total residual forcing",
        },
        {
            "parameter": "dma_data_bytes",
            "current_value": system_model.dma_data_bytes,
            "suggested_value": system_model.dma_data_bytes,
            "unit": "bytes",
            "fit_status": "kept_from_active_model",
            "fit_basis": "interface width should come from RTL, not fitted from timing",
        },
        {
            "parameter": "dma_maxburst",
            "current_value": system_model.dma_maxburst,
            "suggested_value": system_model.dma_maxburst,
            "unit": "beats",
            "fit_status": "kept_from_active_model",
            "fit_basis": "burst policy should be verified from DMA RTL/testbench",
        },
        {
            "parameter": "dma_fsm_overhead_cycles",
            "current_value": system_model.dma_fsm_overhead_cycles,
            "suggested_value": suggested_fsm,
            "unit": "cycles",
            "fit_status": fit_status,
            "fit_basis": f"dma_phase_samples={len(dma_samples)}",
        },
        {
            "parameter": "dma_burst_overhead_cycles",
            "current_value": system_model.dma_burst_overhead_cycles,
            "suggested_value": suggested_burst,
            "unit": "cycles/burst",
            "fit_status": fit_status,
            "fit_basis": f"dma_phase_samples={len(dma_samples)}",
        },
        {
            "parameter": "cpu_config_write_cycles",
            "current_value": system_model.cpu_config_write_cycles,
            "suggested_value": suggested_config,
            "unit": "cycles/write",
            "fit_status": fit_status if config_per_write else "insufficient_measurements",
            "fit_basis": f"config_phase_samples={len(config_per_write)}",
        },
        {
            "parameter": "mac_config_writes",
            "current_value": system_model.mac_config_writes,
            "suggested_value": system_model.mac_config_writes,
            "unit": "writes",
            "fit_status": "kept_from_active_model",
            "fit_basis": "configuration sequence count should come from RTL/software driver",
        },
        {
            "parameter": "system_model_status",
            "current_value": system_model.system_model_status,
            "suggested_value": "candidate_fitted_from_system_calibration",
            "unit": "",
            "fit_status": fit_status,
            "fit_basis": f"rows={len(rows)}; measured_phase_samples={used_rows}",
        },
        {
            "parameter": "system_model_note",
            "current_value": system_model.system_model_note,
            "suggested_value": f"Candidate fitted from {path}",
            "unit": "",
            "fit_status": fit_status,
            "fit_basis": "Must be re-run through --system-calibration before any paper main-table use.",
        },
    ]


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


def build_rtl_validation_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_csv(path)
    details: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    intervals: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        status = row.get("direct_status") or row.get("status") or ""
        if status != "rtl_clean_direct":
            if status:
                blocked.append(
                    {
                        "case": row.get("case", ""),
                        "workload_id": row.get("workload_id", ""),
                        "operator": row.get("operator", ""),
                        "workmode": row.get("workmode", ""),
                        "k": row.get("k", ""),
                        "cout": row.get("cout", ""),
                        "cin_idx_total": row.get("cin_idx_total", ""),
                        "spatial_points": row.get("spatial_points", ""),
                        "direct_status": status,
                        "projected_group16_v7_cycles": row.get("projected_group16_v7_cycles", ""),
                        "x_count": row.get("x_count", ""),
                        "zero_cycles": row.get("zero_cycles", ""),
                        "observed_cycle_prefix": row.get("cycle_list", ""),
                        "blocked_reason": row.get("blocked_reason", ""),
                        "paper_use_policy": "exclude_from_main_performance_tables",
                    }
                )
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
    return details, blocked, intervals


def summarize_validation(rows: list[dict[str, Any]], blocked_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    blocked_rows = blocked_rows or []
    total = len(rows)
    passed = sum(1 for row in rows if row.get("validation_status") == "pass")
    max_abs_error = max((abs(int(row["cycle_error"])) for row in rows), default=0)
    return [
        {
            "rtl_clean_cases": total,
            "passed_cases": passed,
            "failed_cases": total - passed,
            "direct_blocked_cases": len(blocked_rows),
            "blocked_x_cases": sum(1 for row in blocked_rows if fnum(row.get("x_count")) > 0),
            "blocked_zero_cycle_cases": sum(1 for row in blocked_rows if fnum(row.get("zero_cycles")) > 0),
            "pass_rate_percent": round(passed / total * 100.0, 4) if total else 0.0,
            "max_abs_cycle_error": max_abs_error,
            "validation_scope": "direct RTL-clean MAC datapath cases plus explicit blocked-case exclusion list",
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


def paper_use_policy(row: dict[str, Any], value_status: str) -> tuple[str, str]:
    grade = str(row.get("confidence_grade", ""))
    sim_status = str(row.get("sim_status", ""))
    if sim_status != "ok":
        return "exclude_from_paper_tables", f"sim_status={sim_status}"
    if grade.startswith("D_"):
        return "exclude_from_main_performance_tables", str(row.get("confidence_note", "blocked or invalid direct RTL evidence"))
    if value_status not in {"pass", "missing_evidence"}:
        return "exclude_until_value_check_passes", f"value_check_status={value_status}"
    if grade.startswith("B_"):
        if value_status == "pass":
            return "main_table_candidate", "direct RTL-clean timing and output-value check passed"
        return "cycle_only_main_candidate_pending_value_check", "direct RTL-clean timing, but output-value evidence is still missing"
    if grade.startswith("C_"):
        return "appendix_projection_only", "calibrated projection without exact direct RTL-clean workload evidence"
    return "manual_review_required", f"unrecognized confidence_grade={grade}"


def write_paper_tables(out_dir: Path, summary_rows: list[dict[str, Any]], system_interval_rows: list[dict[str, Any]], value_summary: list[dict[str, Any]]) -> None:
    paper_dir = out_dir / "paper_tables"
    value_status = str((value_summary[0] if value_summary else {}).get("value_check_status", "missing_evidence"))

    latency_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    gate_counts: dict[tuple[str, str], int] = {}
    for row in summary_rows:
        policy, reason = paper_use_policy(row, value_status)
        grade = str(row.get("confidence_grade", ""))
        gate_counts[(grade, policy)] = gate_counts.get((grade, policy), 0) + 1
        out = {
            "workload_id": row.get("id", ""),
            "operator": row.get("operator", ""),
            "source_stage": row.get("source_stage", ""),
            "shape_args": row.get("shape_args", ""),
            "pytorchsim_cycles": row.get("pytorchsim_cycles", ""),
            "flood_mac_cycles": row.get("mac_total_cycles", ""),
            "flood_system_cycles": row.get("system_total_cycles", ""),
            "mac_speedup_vs_pytorchsim": row.get("speedup_vs_pytorchsim_cycles", ""),
            "system_speedup_vs_pytorchsim": row.get("system_speedup_vs_pytorchsim_cycles", ""),
            "latency_us_330mhz": row.get("latency_us_330mhz", ""),
            "system_latency_us_330mhz": row.get("system_latency_us_330mhz", ""),
            "confidence_grade": grade,
            "value_check_status": value_status,
            "paper_use_policy": policy,
            "paper_use_reason": reason,
            "model_scope": row.get("model_scope", ""),
        }
        latency_rows.append(out)
        if policy != "main_table_candidate":
            rejected_rows.append(out)

    phase_by_workload: dict[str, dict[str, Any]] = {}
    for event in system_interval_rows:
        wid = str(event.get("workload_id", ""))
        phase = str(event.get("phase", ""))
        duration = int(fnum(event.get("duration_cycles")))
        bucket = phase_by_workload.setdefault(
            wid,
            {
                "workload_id": wid,
                "config_cycles": 0,
                "activation_load_cycles": 0,
                "weight_load_cycles": 0,
                "compute_cycles": 0,
                "output_store_cycles": 0,
                "system_total_cycles": 0,
            },
        )
        bucket["system_total_cycles"] += duration
        if phase == "cpu_config_writes":
            bucket["config_cycles"] += duration
        elif phase == "dma_activation_load":
            bucket["activation_load_cycles"] += duration
        elif phase == "dma_weight_load":
            bucket["weight_load_cycles"] += duration
        elif phase == "mac_datapath_run":
            bucket["compute_cycles"] += duration
        elif phase == "dma_output_store":
            bucket["output_store_cycles"] += duration

    summary_by_id = {str(row.get("id", "")): row for row in summary_rows}
    breakdown_rows: list[dict[str, Any]] = []
    for wid, row in phase_by_workload.items():
        total = int(fnum(row.get("system_total_cycles")))
        source = summary_by_id.get(wid, {})
        policy, reason = paper_use_policy(source, value_status) if source else ("manual_review_required", "missing summary row")
        memory = int(row["activation_load_cycles"]) + int(row["weight_load_cycles"]) + int(row["output_store_cycles"])
        breakdown_rows.append(
            {
                **row,
                "memory_dma_cycles": memory,
                "compute_ratio": round(int(row["compute_cycles"]) / total, 6) if total else "",
                "memory_ratio": round(memory / total, 6) if total else "",
                "confidence_grade": source.get("confidence_grade", ""),
                "system_model_status": source.get("system_model_status", ""),
                "paper_use_policy": "appendix_system_projection" if policy.startswith("main") else policy,
                "paper_use_reason": "system intervals are not direct full-chip RTL-clean evidence; use as diagnostic unless calibrated",
                "base_cycle_policy": reason,
            }
        )

    gate_rows = [
        {
            "confidence_grade": grade,
            "paper_use_policy": policy,
            "rows": count,
            "value_check_status": value_status,
        }
        for (grade, policy), count in sorted(gate_counts.items())
    ]
    gate_rows.append(
        {
            "confidence_grade": "TOTAL",
            "paper_use_policy": "all_rows",
            "rows": len(summary_rows),
            "value_check_status": value_status,
        }
    )

    manifest_rows = [
        {
            "file": "fig6_latency_candidates.csv",
            "purpose": "Fig.6 latency/speedup candidate table with paper-use policy per row",
            "paper_status": "requires filtering by paper_use_policy",
        },
        {
            "file": "fig4_state_breakdown.csv",
            "purpose": "Fig.4 state-cycle breakdown from system intervals",
            "paper_status": "diagnostic until full-chip RTL calibrated",
        },
        {
            "file": "fig3_evidence_gate.csv",
            "purpose": "Fig.3 provenance and confidence gate counts",
            "paper_status": "audit table",
        },
        {
            "file": "rejected_or_appendix_rows.csv",
            "purpose": "Rows excluded from main tables or limited to appendix/projection",
            "paper_status": "must not be silently mixed into main plots",
        },
    ]

    write_csv(paper_dir / "fig6_latency_candidates.csv", latency_rows)
    write_csv(paper_dir / "fig4_state_breakdown.csv", breakdown_rows)
    write_csv(paper_dir / "fig3_evidence_gate.csv", gate_rows)
    write_csv(paper_dir / "rejected_or_appendix_rows.csv", rejected_rows)
    write_csv(paper_dir / "manifest.csv", manifest_rows)


def write_system_calibration_template(out_dir: Path, summary_rows: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for row in summary_rows:
        if row.get("sim_status") != "ok":
            continue
        rows.append(
            {
                "workload_id": row.get("id", ""),
                "operator": row.get("operator", ""),
                "shape_args": row.get("shape_args", ""),
                "predicted_config_cycles": row.get("config_cycles", ""),
                "measured_config_cycles": "",
                "predicted_activation_dma_cycles": row.get("activation_dma_cycles", ""),
                "measured_activation_dma_cycles": "",
                "predicted_weight_dma_cycles": row.get("weight_dma_cycles", ""),
                "measured_weight_dma_cycles": "",
                "predicted_mac_cycles": row.get("mac_total_cycles", ""),
                "measured_mac_cycles": "",
                "predicted_output_dma_cycles": row.get("output_dma_cycles", ""),
                "measured_output_dma_cycles": "",
                "predicted_system_total_cycles": row.get("system_total_cycles", ""),
                "measured_system_total_cycles": "",
                "rtl_status": "",
                "notes": "Fill measured_* fields from full-chip RTL/testbench logs, then run --system-calibration on this CSV.",
            }
        )
    write_csv(out_dir / "system_calibration_template.csv", rows)


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
        "- `system_calibration_template.csv`: optional fill-in CSV for full-chip RTL/testbench measurements when `--include-system` is enabled.",
        "- `hardware_profile.csv`: explicit hardware constants and evidence grade used by this run.",
        "- `value_check_summary.csv`: output-value correctness status, emitted as missing_evidence unless golden and RTL value files are provided.",
        "- `paper_tables/`: optional plot-oriented CSVs with explicit paper-use policy when `--emit-paper-tables` is enabled.",
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
        f"- direct_blocked_cases: {row.get('direct_blocked_cases', 0)}",
        f"- blocked_x_cases: {row.get('blocked_x_cases', 0)}",
        f"- blocked_zero_cycle_cases: {row.get('blocked_zero_cycle_cases', 0)}",
        f"- pass_rate_percent: {row.get('pass_rate_percent', 0)}",
        f"- max_abs_cycle_error: {row.get('max_abs_cycle_error', 0)}",
        "",
        "## Scope",
        "",
        "This validates the modeled MAC-machine run timing against direct RTL-clean evidence only.",
        "Blocked direct RTL attempts are listed separately and excluded from paper main performance tables.",
        "It does not validate DMA, CPU software control, SRAM data correctness, softmax, sparsity, or zero-skip.",
        "",
    ]
    out_dir.joinpath("README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="", help="CSV with operator and shape_args columns.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--cycle-trace-cap", type=int, default=0)
    parser.add_argument("--rtl-validation", default="", help="Optional direct RTL-clean validation CSV.")
    parser.add_argument("--system-calibration", default="", help="Optional full-chip/system calibration CSV with measured_* cycle columns.")
    parser.add_argument("--system-model", default="", help="Optional CSV parameter file overriding system DMA/config model constants.")
    parser.add_argument("--include-system", action="store_true", help="Emit unvalidated CPU config + DMA/SRAM system intervals.")
    parser.add_argument("--golden-values", default="", help="Optional golden numeric output file for value checking.")
    parser.add_argument("--rtl-values", default="", help="Optional RTL numeric output file for value checking.")
    parser.add_argument("--value-rtol", type=float, default=0.0)
    parser.add_argument("--value-atol", type=float, default=0.0)
    parser.add_argument("--value-check-only", action="store_true", help="Only run output-value checker.")
    parser.add_argument("--emit-paper-tables", action="store_true", help="Emit plot-oriented paper CSVs with confidence gates.")
    args = parser.parse_args()
    system_model = read_system_model(Path(args.system_model) if args.system_model else None)

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
        write_hardware_profile(out_dir, system_model)
        write_system_model_template(out_dir, system_model)
        print(f"wrote FLOOD value check to {out_dir}")
        return

    if args.rtl_validation:
        out_dir = Path(args.out_dir)
        details, blocked, intervals = build_rtl_validation_rows(Path(args.rtl_validation))
        summary = summarize_validation(details, blocked)
        write_csv(out_dir / "rtl_validation_details.csv", details)
        write_csv(out_dir / "rtl_blocked_cases.csv", blocked)
        write_csv(out_dir / "rtl_validation_summary.csv", summary)
        write_csv(out_dir / "rtl_validation_intervals.csv", intervals)
        write_hardware_profile(out_dir, system_model)
        write_system_model_template(out_dir, system_model)
        write_validation_readme(out_dir, summary)
        print(f"wrote FLOOD cycle simulator RTL validation to {out_dir}")
        return

    if args.system_calibration:
        out_dir = Path(args.out_dir)
        details, summary = build_system_calibration_rows(Path(args.system_calibration), system_model)
        suggestions = build_system_model_suggestion_rows(Path(args.system_calibration), system_model)
        write_csv(out_dir / "system_calibration_details.csv", details)
        write_csv(out_dir / "system_calibration_summary.csv", summary)
        write_csv(out_dir / "system_model_suggestion.csv", suggestions)
        write_hardware_profile(out_dir, system_model)
        write_system_model_template(out_dir, system_model)
        print(f"wrote FLOOD system calibration report to {out_dir}")
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
                system_events, system = simulate_system_events(wid, shape, int(flood_cycles), system_model)
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
    write_hardware_profile(out_dir, system_model)
    write_system_model_template(out_dir, system_model)
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
        write_system_calibration_template(out_dir, summary)
    if args.emit_paper_tables:
        write_paper_tables(out_dir, summary, system_interval_rows, value_summary)
    if args.cycle_trace_cap:
        write_csv(out_dir / "cycle_trace.csv", cycle_rows)
    write_readme(out_dir, summary, args.cycle_trace_cap)
    print(f"wrote FLOOD cycle simulator output to {out_dir}")


if __name__ == "__main__":
    main()
