#!/usr/bin/env python3
"""Build execution, timing, and output-hash consistency gates for RTL repeats."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path


DONE_RE = re.compile(r"Done interrupt after\s+(\d+)\s+cycles", re.IGNORECASE)


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
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def case_hash(case_dir: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(case_dir.glob("actual_*.csv")):
        h.update(path.name.encode("utf-8"))
        h.update(sha256_file(path).encode("ascii"))
    return h.hexdigest()


def parse_cycles(log_path: Path) -> list[int]:
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    return [int(x) for x in DONE_RE.findall(text)]


def build_gate(server_root: Path, out_dir: Path) -> None:
    status_rows = read_rows(server_root / "results" / "value_repeat_status.csv")
    cases = sorted({row.get("case_id", "") for row in status_rows if row.get("case_id")})
    by_case_pass = {(row.get("case_id", ""), row.get("pass_name", "")): row for row in status_rows}
    detail_rows: list[dict[str, str]] = []
    for case in cases:
        golden = by_case_pass.get((case, "golden"), {})
        rtl = by_case_pass.get((case, "rtl"), {})
        execution_clean = (
            golden.get("rc") == "0"
            and rtl.get("rc") == "0"
            and golden.get("timeout") == "no"
            and rtl.get("timeout") == "no"
        )
        golden_log = server_root / "logs" / f"{case}_golden.log"
        rtl_log = server_root / "logs" / f"{case}_rtl.log"
        golden_cycles = parse_cycles(golden_log)
        rtl_cycles = parse_cycles(rtl_log)
        timing_pass = bool(golden_cycles) and golden_cycles == rtl_cycles
        golden_hash = case_hash(server_root / "golden" / case)
        rtl_hash = case_hash(server_root / "rtl" / case)
        hash_pass = bool(golden_hash) and golden_hash == rtl_hash
        detail_rows.append(
            {
                "case_id": case,
                "execution_status": "pass" if execution_clean else "fail",
                "golden_cycles": ";".join(str(x) for x in golden_cycles),
                "rtl_cycles": ";".join(str(x) for x in rtl_cycles),
                "timing_repeat_status": "pass" if timing_pass else "fail",
                "golden_output_sha256": golden_hash,
                "rtl_output_sha256": rtl_hash,
                "output_hash_status": "pass" if hash_pass else "fail",
                "ready_for_direct_paper_data": "no",
                "paper_data_blocker": "repeatability_not_full_chip_independent_golden",
            }
        )

    execution_pass = sum(1 for row in detail_rows if row["execution_status"] == "pass")
    timing_pass = sum(1 for row in detail_rows if row["timing_repeat_status"] == "pass")
    hash_pass = sum(1 for row in detail_rows if row["output_hash_status"] == "pass")
    summary = [
        {
            "repeat_consistency_status": "pass"
            if detail_rows and execution_pass == timing_pass == hash_pass == len(detail_rows)
            else "missing_or_failed",
            "cases": str(len(detail_rows)),
            "execution_clean_cases": str(execution_pass),
            "timing_repeat_pass_cases": str(timing_pass),
            "output_hash_pass_cases": str(hash_pass),
            "direct_paper_ready_cases": "0",
            "paper_data_policy": "repeatability_only_not_full_chip_independent_golden",
        }
    ]
    write_csv(out_dir / "rtl_repeat_consistency_detail.csv", detail_rows)
    write_csv(out_dir / "rtl_repeat_consistency_summary.csv", summary)
    readme = """# RTL Repeat Consistency Gate

This gate checks three server-repeat properties for captured P0 tile cases:

- both RTL executions finished cleanly,
- both executions produced identical done-cycle lists,
- both executions produced identical output-file hashes.

The evidence supports repeatability. It is still not independent software
golden evidence and does not make rows direct paper data.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", default="results/flood_cycle_sim_v1/server_rtl_value_repeat_v1")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/rtl_repeat_consistency_gate")
    args = parser.parse_args()
    build_gate(Path(args.server_root), Path(args.out_dir))


if __name__ == "__main__":
    main()
