#!/usr/bin/env python3
"""Parse RTL/testbench logs into FLOOD system calibration CSV rows.

This script fills the `measured_*` columns expected by
`flood_local/flood_cycle_sim.py --system-calibration`.

Preferred log markers are explicit and phase named:

    FLOOD_CONFIG_CYCLES: 3
    FLOOD_ACTIVATION_DMA_CYCLES: 16
    FLOOD_WEIGHT_DMA_CYCLES: 2638
    FLOOD_MAC_CYCLES: 223
    FLOOD_OUTPUT_DMA_CYCLES: 46
    FLOOD_SYSTEM_TOTAL_CYCLES: 2926
    FLOOD_RTL_STATUS: full_chip_clean

The parser also accepts a few generic total-cycle fallbacks, but split phase
cycles should come from explicit markers to avoid hiding unmodeled stalls.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any


PHASE_PATTERNS = {
    "measured_config_cycles": [
        r"FLOOD_CONFIG_CYCLES\s*[:=]\s*(\d+)",
        r"CONFIG(?:_|\s+)CYCLES\s*[:=]\s*(\d+)",
    ],
    "measured_activation_dma_cycles": [
        r"FLOOD_ACTIVATION_DMA_CYCLES\s*[:=]\s*(\d+)",
        r"ACTIVATION(?:_|\s+)DMA(?:_|\s+)CYCLES\s*[:=]\s*(\d+)",
    ],
    "measured_weight_dma_cycles": [
        r"FLOOD_WEIGHT_DMA_CYCLES\s*[:=]\s*(\d+)",
        r"WEIGHT(?:_|\s+)DMA(?:_|\s+)CYCLES\s*[:=]\s*(\d+)",
    ],
    "measured_mac_cycles": [
        r"FLOOD_MAC_CYCLES\s*[:=]\s*(\d+)",
        r"MAC(?:_|\s+)CYCLES\s*[:=]\s*(\d+)",
    ],
    "measured_output_dma_cycles": [
        r"FLOOD_OUTPUT_DMA_CYCLES\s*[:=]\s*(\d+)",
        r"OUTPUT(?:_|\s+)DMA(?:_|\s+)CYCLES\s*[:=]\s*(\d+)",
    ],
    "measured_system_total_cycles": [
        r"FLOOD_SYSTEM_TOTAL_CYCLES\s*[:=]\s*(\d+)",
        r"SYSTEM(?:_|\s+)TOTAL(?:_|\s+)CYCLES\s*[:=]\s*(\d+)",
        r"Total execution cycles:\s*(\d+)",
        r"\[INTR\].*?(?:cycle|cycles)\s*[:=]\s*(\d+)",
    ],
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


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


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def parse_log(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    out = {field: first_match(text, patterns) for field, patterns in PHASE_PATTERNS.items()}
    status = first_match(text, [r"FLOOD_RTL_STATUS\s*[:=]\s*([A-Za-z0-9_./-]+)", r"RTL_STATUS\s*[:=]\s*([A-Za-z0-9_./-]+)"])
    if not status:
        if re.search(r"Simulation (?:Done|Passed)", text, flags=re.IGNORECASE):
            status = "simulation_done"
        elif text:
            status = "parsed_log_no_status"
        else:
            status = "missing_log"
    out["rtl_status"] = status
    missing = [field for field, value in out.items() if field.startswith("measured_") and not value]
    out["parse_status"] = "pass" if not missing else "missing_fields"
    out["missing_fields"] = ";".join(missing)
    return out


def log_map_by_workload(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    rows = read_csv(path)
    mapping: dict[str, str] = {}
    for row in rows:
        wid = row.get("workload_id") or row.get("id") or row.get("workload")
        log_file = row.get("log_file") or row.get("rtl_log") or row.get("path")
        if wid and log_file:
            mapping[wid] = log_file
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True, help="system_calibration_template.csv or compatible CSV.")
    parser.add_argument("--log-map", default="", help="CSV with workload_id,log_file columns. Optional if template has log_file.")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    template = Path(args.template)
    rows = read_csv(template)
    mapping = log_map_by_workload(Path(args.log_map) if args.log_map else None)
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        wid = row.get("workload_id") or row.get("id") or row.get("workload") or ""
        log_file = row.get("log_file") or mapping.get(wid, "")
        parsed = parse_log(Path(log_file)) if log_file else {
            "rtl_status": "missing_log",
            "parse_status": "missing_log",
            "missing_fields": ";".join(PHASE_PATTERNS),
        }
        out = dict(row)
        out["log_file"] = log_file
        for key, value in parsed.items():
            if key.startswith("measured_") and value:
                out[key] = value
            elif key in {"rtl_status", "parse_status", "missing_fields"}:
                out[key] = value
        out_rows.append(out)

    write_csv(Path(args.out), out_rows)
    print(f"wrote parsed system calibration CSV to {args.out}")


if __name__ == "__main__":
    main()
