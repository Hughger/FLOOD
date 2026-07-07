#!/usr/bin/env python3
"""Build conservative profiles for quantization and outlier mechanisms."""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any


CONFIG_PARAMETERS = [
    "rowSize",
    "colSize",
    "dataWidth",
    "outputWidth",
    "finalWidth",
    "weightBandWidth",
    "featureMapBandWidth",
    "outputBufferDataWidth",
]

SOURCE_PATTERNS = {
    "quantization_unit": r"QuantizationUnit|QuantizationConfigurator|MACArrayWithQuantization",
    "quantization_params": r"multiplier|shiftAmount|zeroPoint|scale",
    "int8": r"INT8|int8|8-bit|8bit|8位",
    "int4": r"INT4|int4|4-bit|4bit|4位",
    "packed_nibble": r"nibble|packed|pack|4\s*\*|bandWidth\s*=\s*4",
    "outlier": r"outlier|Outlier|异常值|离群",
    "threshold": r"threshold|Threshold|clip|clamp|saturat|阈值|截断|饱和",
    "python_quantize": r"def\s+quantize|write_quantized|bitwidth",
}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


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


def extract_config(path: Path) -> dict[str, str]:
    text = read_text(path)
    values: dict[str, str] = {}
    for name in CONFIG_PARAMETERS:
        match = re.search(rf"\bval\s+{re.escape(name)}\s*=\s*([^\n/]+)", text)
        values[name] = match.group(1).strip().rstrip(",") if match else "MISSING"
    return values


def source_files(root: Path) -> list[Path]:
    explicit = [
        root / "src" / "main" / "scala" / "core" / "Config.scala",
        root / "src" / "main" / "scala" / "core" / "CIMcore.scala",
        root / "src" / "main" / "scala" / "Machine" / "OutRouterPlane.scala",
        root / "src" / "main" / "scala" / "Machine" / "OutRouterPlanePost.scala",
        root / "QuantizationModule使用说明.md",
        root / "MacMachine使用说明文档.md",
        root / "README.md",
    ]
    files = [path for path in explicit if path.exists()]
    for folder in [root / "src" / "python", root / "src" / "tmp" / "core", root / "src" / "tmp" / "sram"]:
        if folder.exists():
            files.extend(path for path in folder.rglob("*") if path.suffix in {".py", ".scala", ".md"})
    return files


def count_patterns(paths: list[Path]) -> dict[str, int]:
    text = "\n".join(read_text(path) for path in paths)
    return {name: len(re.findall(pattern, text, flags=re.IGNORECASE)) for name, pattern in SOURCE_PATTERNS.items()}


def build_profile(base_root: Path, mechanism_name: str, mechanism_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    base_config = extract_config(base_root / "src" / "main" / "scala" / "core" / "Config.scala")
    mech_config = extract_config(mechanism_root / "src" / "main" / "scala" / "core" / "Config.scala")
    config_rows = [
        {
            "mechanism": mechanism_name,
            "parameter": parameter,
            "base_value": base_config.get(parameter, "MISSING"),
            "mechanism_value": mech_config.get(parameter, "MISSING"),
            "changed": base_config.get(parameter, "MISSING") != mech_config.get(parameter, "MISSING"),
        }
        for parameter in CONFIG_PARAMETERS
    ]

    base_counts = count_patterns(source_files(base_root))
    mech_counts = count_patterns(source_files(mechanism_root))
    evidence_rows = [
        {
            "mechanism": mechanism_name,
            "pattern": pattern_name,
            "base_count": base_counts[pattern_name],
            "mechanism_count": mech_counts[pattern_name],
            "changed": base_counts[pattern_name] != mech_counts[pattern_name],
        }
        for pattern_name in SOURCE_PATTERNS
    ]

    detected: list[str] = []
    if mech_counts["quantization_unit"] > base_counts["quantization_unit"]:
        detected.append("quantization_unit_material")
    if mech_counts["int4"] > base_counts["int4"] or mech_counts["packed_nibble"] > base_counts["packed_nibble"]:
        detected.append("int4_or_packed_material")
    if mech_counts["outlier"] > base_counts["outlier"]:
        detected.append("outlier_material")
    if mech_counts["python_quantize"] > base_counts["python_quantize"]:
        detected.append("python_quantization_reference")

    gate = {
        "mechanism": mechanism_name,
        "simulator_status": "profile_only_not_enabled",
        "detected_features": ";".join(detected) if detected else "no_integrated_quant_outlier_feature_detected",
        "confidence_grade": f"D_{mechanism_name}_quality_timing_not_validated",
        "paper_use_policy": "exclude_from_main_performance_tables",
        "required_to_enable": "requires workload quantization config, accuracy/error metrics, output-value pass, and RTL/testbench timing; power claims require activity or gate-level power evidence",
    }
    return config_rows, evidence_rows, gate


def write_readme(out_dir: Path) -> None:
    out_dir.joinpath("README.md").write_text(
        "\n".join(
            [
                "# Quantization and outlier mechanism profiles",
                "",
                "Generated by `flood_local/build_quant_outlier_profiles.py`.",
                "",
                "These files are evidence inventory only.  They do not change cycle-simulator latency.",
                "Quantization/outlier rows require both performance evidence and accuracy/error evidence before paper use.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-root", default="FLOOD")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--mechanism", action="append", nargs=2, metavar=("NAME", "ROOT"), required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    config_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    for name, root in args.mechanism:
        cfg, ev, gate = build_profile(Path(args.base_root), name, Path(root))
        config_rows.extend(cfg)
        evidence_rows.extend(ev)
        gates.append(gate)

    write_csv(out_dir / "quant_outlier_config_profile.csv", config_rows)
    write_csv(out_dir / "quant_outlier_source_evidence.csv", evidence_rows)
    write_csv(out_dir / "quant_outlier_paper_gate.csv", gates)
    write_readme(out_dir)
    print(f"wrote quantization/outlier mechanism profiles to {out_dir}")


if __name__ == "__main__":
    main()
