#!/usr/bin/env python3
"""Merge workload, value, and system gates into a final paper-data gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


REQUIRED_COLUMNS = {"paper_row_id", "workload_id", "value_workload_id", "system_calibration_id"}


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


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


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(role: str, path: Path) -> dict[str, str]:
    return {
        "role": role,
        "path": str(path),
        "exists": str(path.exists()),
        "bytes": str(path.stat().st_size) if path.exists() and path.is_file() else "0",
        "sha256": sha256_file(path),
    }


def by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if value and value not in out:
            out[value] = row
    return out


def validate_manifest(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise SystemExit("Paper data gate manifest is empty.")
    missing = REQUIRED_COLUMNS - set(rows[0].keys())
    if missing:
        raise SystemExit(f"Paper data gate manifest missing required columns: {', '.join(sorted(missing))}")


def build_gate(
    manifest: Path,
    workload_gate: Path,
    value_gate: Path,
    system_gate: Path,
    out_dir: Path,
) -> None:
    manifest_rows = read_rows(manifest)
    validate_manifest(manifest_rows)
    workloads = by_key(read_rows(workload_gate), "workload_id")
    values = by_key(read_rows(value_gate), "workload_id")
    systems = by_key(read_rows(system_gate), "calibration_id")

    final_rows: list[dict[str, str]] = []
    for row in manifest_rows:
        paper_row_id = row["paper_row_id"]
        workload_id = row["workload_id"]
        value_id = row["value_workload_id"]
        system_id = row["system_calibration_id"]
        workload = workloads.get(workload_id, {})
        value = values.get(value_id, {})
        system = systems.get(system_id, {})

        blockers: list[str] = []
        workload_policy = workload.get("main_figure_ready_policy", "missing_workload_gate")
        value_policy = value.get("main_value_ready_policy", "missing_value_gate")
        system_policy = system.get("paper_system_timing_policy", "missing_system_gate")

        if workload_policy != "ready_for_main_figure":
            blockers.append(f"workload={workload_policy}")
            if workload.get("main_figure_blockers"):
                blockers.append(workload["main_figure_blockers"])
        if value_policy != "ready_for_main_figure_value":
            blockers.append(f"value={value_policy}")
            if value.get("blockers"):
                blockers.append(value["blockers"])
        if system_policy != "ready_for_main_figure_system_timing":
            blockers.append(f"system={system_policy}")
            if system.get("blockers"):
                blockers.append(system["blockers"])

        ready = not blockers
        final_rows.append(
            {
                "paper_row_id": paper_row_id,
                "workload_id": workload_id,
                "value_workload_id": value_id,
                "system_calibration_id": system_id,
                "workload_policy": workload_policy,
                "value_policy": value_policy,
                "system_policy": system_policy,
                "main_table_candidate_rows": workload.get("main_table_candidate_rows", "0"),
                "final_paper_data_policy": "ready_for_main_figure" if ready else "not_ready_for_main_figure",
                "blockers": ";".join(blockers),
                "notes": row.get("notes", ""),
            }
        )

    write_csv(out_dir / "final_paper_data_gate.csv", final_rows)
    ready_rows = [row for row in final_rows if row["final_paper_data_policy"] == "ready_for_main_figure"]
    summary = [
        {
            "paper_rows": str(len(final_rows)),
            "ready_for_main_figure": str(len(ready_rows)),
            "not_ready_for_main_figure": str(len(final_rows) - len(ready_rows)),
            "ready_percent": f"{(len(ready_rows) / len(final_rows) * 100.0) if final_rows else 0.0:.2f}",
            "policy": "Only final_paper_data_policy=ready_for_main_figure may enter main paper figures.",
        }
    ]
    write_csv(out_dir / "final_paper_data_summary.csv", summary)
    evidence_files = [
        file_record("input_manifest", manifest),
        file_record("input_workload_gate", workload_gate),
        file_record("input_value_gate", value_gate),
        file_record("input_system_gate", system_gate),
        file_record("output_final_gate", out_dir / "final_paper_data_gate.csv"),
        file_record("output_final_summary", out_dir / "final_paper_data_summary.csv"),
    ]
    write_csv(out_dir / "evidence_manifest.csv", evidence_files)
    text = f"""# FLOOD Final Paper Data Gate

Manifest: `{manifest}`

This gate merges three independent checks:

1. workload timing/paper-use gate
2. output value-correctness gate
3. full-chip/system timing calibration gate

Generated files:

- `final_paper_data_gate.csv`: one row per planned paper data row.
- `final_paper_data_summary.csv`: compact ready/not-ready count.
- `evidence_manifest.csv`: source/output file sizes and SHA256 hashes.

Main-figure rule: only rows with `final_paper_data_policy=ready_for_main_figure`
may enter main paper figures.
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--workload-gate", required=True)
    parser.add_argument("--value-gate", required=True)
    parser.add_argument("--system-gate", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    build_gate(
        Path(args.manifest),
        Path(args.workload_gate),
        Path(args.value_gate),
        Path(args.system_gate),
        Path(args.out_dir),
    )


if __name__ == "__main__":
    main()
