#!/usr/bin/env python3
"""Adversarially audit a FLOOD main-figure export package."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


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


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "0") or 0))
    except ValueError:
        return 0


def row_id(row: dict[str, str]) -> str:
    return row.get("paper_row_id", "")


def audit_export(final_gate: Path, export_dir: Path, out_dir: Path) -> int:
    final_rows = read_rows(final_gate)
    main_rows = read_rows(export_dir / "main_figure_rows.csv")
    rejected_rows = read_rows(export_dir / "rejected_rows.csv")
    export_summary = first_row(export_dir / "export_summary.csv")

    approved_ids = {row_id(row) for row in final_rows if row.get("final_paper_data_policy") == "ready_for_main_figure"}
    rejected_ids = {row_id(row) for row in final_rows if row.get("final_paper_data_policy") != "ready_for_main_figure"}
    main_ids = {row_id(row) for row in main_rows}
    exported_rejected_ids = sorted(main_ids & rejected_ids)
    missing_approved_ids = sorted(approved_ids - main_ids)
    extra_exported_ids = sorted(main_ids - approved_ids)
    rejected_file_ids = {row_id(row) for row in rejected_rows}

    actual_hash = sha256_file(final_gate)
    summary_hash = export_summary.get("source_final_gate_sha256", "")
    actual_hardware_sigs = sorted({row.get("hardware_source_signature_sha256", "") for row in final_rows if row.get("hardware_source_signature_sha256", "")})
    summary_hardware_sigs = sorted(sig for sig in export_summary.get("hardware_source_signature_sha256", "").split(";") if sig)

    checks = [
        {
            "check": "source_final_gate_exists",
            "status": "pass" if final_gate.exists() and final_rows else "fail",
            "evidence": f"rows={len(final_rows)}",
        },
        {
            "check": "source_hash_matches_export_summary",
            "status": "pass" if actual_hash and summary_hash == actual_hash else "fail",
            "evidence": f"summary={summary_hash}, actual={actual_hash}",
        },
        {
            "check": "main_rows_are_exact_approved_set",
            "status": "pass" if not extra_exported_ids and not missing_approved_ids else "fail",
            "evidence": f"exported={len(main_rows)}, approved={len(approved_ids)}, extra={';'.join(extra_exported_ids)}, missing={';'.join(missing_approved_ids)}",
        },
        {
            "check": "no_rejected_rows_exported",
            "status": "pass" if not exported_rejected_ids else "fail",
            "evidence": ";".join(exported_rejected_ids),
        },
        {
            "check": "rejected_file_matches_final_gate",
            "status": "pass" if rejected_file_ids == rejected_ids else "fail",
            "evidence": f"rejected_file={len(rejected_file_ids)}, final_rejected={len(rejected_ids)}",
        },
        {
            "check": "export_summary_counts_match_files",
            "status": "pass" if as_int(export_summary, "exported_main_figure_rows") == len(main_rows) and as_int(export_summary, "rejected_rows") == len(rejected_rows) else "fail",
            "evidence": f"summary_exported={export_summary.get('exported_main_figure_rows','')}, file_exported={len(main_rows)}, summary_rejected={export_summary.get('rejected_rows','')}, file_rejected={len(rejected_rows)}",
        },
        {
            "check": "hardware_signature_matches_final_gate",
            "status": "pass" if actual_hardware_sigs == summary_hardware_sigs else "fail",
            "evidence": f"summary={';'.join(summary_hardware_sigs)}, actual={';'.join(actual_hardware_sigs)}",
        },
    ]
    write_csv(out_dir / "main_figure_export_audit.csv", checks)
    failures = [row for row in checks if row["status"] != "pass"]
    summary = [
        {
            "audit_status": "pass" if not failures else "fail",
            "checks": str(len(checks)),
            "failed_checks": str(len(failures)),
            "approved_rows": str(len(approved_ids)),
            "exported_rows": str(len(main_rows)),
            "rejected_rows": str(len(rejected_rows)),
            "source_final_gate_sha256": actual_hash,
            "policy": "Main figure exports must exactly match final_paper_data_policy=ready_for_main_figure rows.",
        }
    ]
    write_csv(out_dir / "main_figure_export_audit_summary.csv", summary)
    readme = f"""# FLOOD Main Figure Export Audit

Final gate: `{final_gate}`
Export directory: `{export_dir}`

This audit is adversarial: it treats the final gate as authoritative and checks
whether `main_figure_rows.csv`, `rejected_rows.csv`, and `export_summary.csv`
could have leaked unapproved rows into paper plots.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    return 0 if not failures else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-gate", required=True)
    parser.add_argument("--export-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    raise SystemExit(audit_export(Path(args.final_gate), Path(args.export_dir), Path(args.out_dir)))


if __name__ == "__main__":
    main()
