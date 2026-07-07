#!/usr/bin/env python3
"""Build conservative profiles for sparsity-like standalone mechanisms.

The generated files are evidence inventory only.  They do not enable timing
effects in the cycle simulator.
"""
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
    "pipeline",
    "tLatency",
    "compressionFactor",
    "tileSize",
    "maxGroupSize",
    "maxGroupNum",
    "maxKernelBlockCout",
    "maxKernelBlockCin",
]

SOURCE_PATTERNS = {
    "activation_zero_flags": r"activation_zero_flags",
    "weight_zero_flags": r"weight_zero_flags",
    "zero_or_condition": r"wZero\s*\|\|\s*aZero|activation_zero_flags|weight_zero_flags",
    "mactree_flood": r"class\s+MACTreeFlood\b",
    "group_size": r"groupSize",
    "group_num": r"groupNum",
    "mask": r"\bmask\b|Mask|MASK",
    "sparse_keyword": r"sparse|sparsity|稀疏|跳零",
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


def count_patterns(paths: list[Path]) -> dict[str, int]:
    text = "\n".join(read_text(path) for path in paths)
    return {name: len(re.findall(pattern, text, flags=re.IGNORECASE)) for name, pattern in SOURCE_PATTERNS.items()}


def source_files(root: Path) -> list[Path]:
    candidates = [
        root / "src" / "main" / "scala" / "core" / "CIMcore.scala",
        root / "src" / "main" / "scala" / "core" / "Config.scala",
        root / "src" / "main" / "scala" / "Machine" / "FSM.scala",
        root / "src" / "main" / "scala" / "Machine" / "MacMachine.scala",
        root / "src" / "main" / "scala" / "Machine" / "OutRouter.scala",
        root / "src" / "main" / "scala" / "Machine" / "OutRouterPlane.scala",
        root / "README.md",
        root / "MacMachine使用说明文档.md",
    ]
    return [path for path in candidates if path.exists()]


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

    has_zero_flags = mech_counts["activation_zero_flags"] > 0 or mech_counts["weight_zero_flags"] > 0
    has_group_logic = mech_counts["group_size"] > base_counts["group_size"] or mech_counts["group_num"] > base_counts["group_num"]
    detected = []
    if has_zero_flags:
        detected.append("zero_flag_inputs")
    if has_group_logic:
        detected.append("group_control_deltas")
    if mech_counts["sparse_keyword"] > base_counts["sparse_keyword"]:
        detected.append("sparsity_keywords")

    gate = {
        "mechanism": mechanism_name,
        "simulator_status": "profile_only_not_enabled",
        "detected_features": ";".join(detected) if detected else "no_strong_sparse_feature_detected",
        "confidence_grade": f"D_{mechanism_name}_timing_not_validated",
        "paper_use_policy": "exclude_from_main_performance_tables",
        "required_to_enable": "direct RTL/testbench timing cycles, output-value pass, and workload-level sparsity statistics; activity counters required for power claims",
    }
    return config_rows, evidence_rows, gate


def write_readme(out_dir: Path) -> None:
    lines = [
        "# Sparsity mechanism profiles",
        "",
        "Generated by `flood_local/build_sparsity_profiles.py`.",
        "",
        "These files are evidence inventory only.  The cycle simulator does not use them to change latency.",
        "",
        "A mechanism may affect paper tables only after timing, value, and workload sparsity evidence pass their gates.",
        "",
    ]
    out_dir.joinpath("README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-root", default="FLOOD")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--mechanism", action="append", nargs=2, metavar=("NAME", "ROOT"), required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    all_config: list[dict[str, Any]] = []
    all_evidence: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    for name, root in args.mechanism:
        config_rows, evidence_rows, gate = build_profile(Path(args.base_root), name, Path(root))
        all_config.extend(config_rows)
        all_evidence.extend(evidence_rows)
        gates.append(gate)

    write_csv(out_dir / "sparsity_config_profile.csv", all_config)
    write_csv(out_dir / "sparsity_source_evidence.csv", all_evidence)
    write_csv(out_dir / "sparsity_paper_gate.csv", gates)
    write_readme(out_dir)
    print(f"wrote sparsity mechanism profiles to {out_dir}")


if __name__ == "__main__":
    main()
