#!/usr/bin/env python3
"""Build a source manifest for RTL/model files that anchor simulator evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


SOURCE_GROUPS = {
    "chisel_mac_model": [
        "src/main/scala/Machine/*.scala",
        "src/main/scala/core/*.scala",
        "src/main/scala/sram/*.scala",
        "src/main/scala/IO/*.scala",
    ],
    "generated_mac_rtl": [
        "rtl/e203/subsys/mac_unit/*.v",
    ],
    "dma_and_subsystem_rtl": [
        "rtl/e203/subsys/dma/*.v",
        "rtl/e203/subsys/e203_subsys_top.v",
        "rtl/e203/subsys/e203_subsys_nice_core.v",
        "rtl/e203/subsys/bus/top/bus_top.v",
    ],
    "cpu_interface_rtl": [
        "rtl/e203/core/e203_exu_nice.v",
        "rtl/e203/core/e203_lsu*.v",
        "rtl/e203/core/e203_biu.v",
        "rtl/e203/core/e203_cpu_top.v",
    ],
    "validation_testbench": [
        "rtl/e203/subsys/mac_unit/tb_*.v",
        "tb/tb_mac_asic.v",
        "tb/tb_top.v",
        "src/test/scala/machine/*.scala",
        "src/test/scala/core/*.scala",
    ],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def build_manifest(base_root: Path, out_dir: Path) -> None:
    rows: list[dict[str, str]] = []
    for group, patterns in SOURCE_GROUPS.items():
        matched: set[Path] = set()
        for pattern in patterns:
            matched.update(path for path in base_root.glob(pattern) if path.is_file())
        if not matched:
            rows.append(
                {
                    "source_group": group,
                    "relative_path": "",
                    "exists": "False",
                    "bytes": "0",
                    "sha256": "",
                    "evidence_role": "missing_expected_source_group",
                }
            )
            continue
        for path in sorted(matched):
            rows.append(
                {
                    "source_group": group,
                    "relative_path": str(path.relative_to(base_root)).replace("\\", "/"),
                    "exists": "True",
                    "bytes": str(path.stat().st_size),
                    "sha256": sha256_file(path),
                    "evidence_role": role_for_group(group),
                }
            )

    write_csv(out_dir / "rtl_source_manifest.csv", rows)
    missing_groups = sorted({row["source_group"] for row in rows if row["exists"] != "True"})
    file_rows = [row for row in rows if row["exists"] == "True"]
    signature_input = "\n".join(f"{row['source_group']}|{row['relative_path']}|{row['sha256']}" for row in file_rows)
    signature = hashlib.sha256(signature_input.encode("utf-8")).hexdigest()
    summary = [
        {
            "base_root": str(base_root),
            "source_groups": str(len(SOURCE_GROUPS)),
            "source_files": str(len(file_rows)),
            "missing_source_groups": str(len(missing_groups)),
            "missing_group_names": ";".join(missing_groups),
            "hardware_source_signature_sha256": signature,
            "policy": "Simulator paper data must be regenerated if this source signature changes.",
        }
    ]
    write_csv(out_dir / "rtl_source_summary.csv", summary)
    (out_dir / "hardware_source_signature.txt").write_text(signature + "\n", encoding="utf-8")
    readme = f"""# FLOOD RTL Source Manifest

This manifest binds simulator evidence to the RTL/Chisel source files that
anchor the current model scope.

Generated files:

- `rtl_source_manifest.csv`: source file paths, sizes, and SHA256 hashes.
- `rtl_source_summary.csv`: source group counts and combined source signature.
- `hardware_source_signature.txt`: combined source signature only.

Policy: if `hardware_source_signature_sha256` changes, old simulator outputs
must not be mixed with newly generated data without rerunning the full gates.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def role_for_group(group: str) -> str:
    if group == "chisel_mac_model":
        return "MAC datapath structure and generator parameters"
    if group == "generated_mac_rtl":
        return "generated MAC-machine RTL and direct validation target"
    if group == "dma_and_subsystem_rtl":
        return "system projection interface and DMA timing basis"
    if group == "cpu_interface_rtl":
        return "CPU/NICE/LSU interface timing context"
    if group == "validation_testbench":
        return "direct RTL/testbench validation context"
    return "source evidence"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-root", default="FLOOD")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/rtl_source_manifest")
    args = parser.parse_args()
    build_manifest(Path(args.base_root), Path(args.out_dir))


if __name__ == "__main__":
    main()
