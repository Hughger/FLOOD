#!/usr/bin/env python3
"""Inventory standalone FLOOD optimization branches for simulator integration.

The six optimization folders are full project copies, not clean patches.  This
script compares each copy against the current base `FLOOD/` tree and emits a
mechanism inventory with simulator integration status.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path
from typing import Any


MECHANISMS = [
    {
        "mechanism": "mactree",
        "root": "mactree/flood",
        "sim_hook": "mac datapath compute interval and first-level adder tree activity",
        "default_policy": "requires_rtl_timing_and_value_validation",
    },
    {
        "mechanism": "outlier",
        "root": "outlier/flood",
        "sim_hook": "outlier ratio, route/shift bypass, output-value checker",
        "default_policy": "requires_quality_and_rtl_value_validation",
    },
    {
        "mechanism": "INT8-INT4",
        "root": "INT8-INT4/flood",
        "sim_hook": "precision mode, packed traffic, MAC throughput, value tolerance",
        "default_policy": "requires_precision_mode_rtl_validation",
    },
    {
        "mechanism": "softmax",
        "root": "softmax/flood",
        "sim_hook": "softmax vector dimension and per-32-lane pipeline cycles",
        "default_policy": "requires_softmax_module_timing_and_value_validation",
    },
    {
        "mechanism": "zero-skip",
        "root": "zero-skip/flood",
        "sim_hook": "activation/weight zero ratio, skipped multiply/add cycles",
        "default_policy": "requires_sparse_counter_or_rtl_trace_validation",
    },
    {
        "mechanism": "channel_group_sparsity",
        "root": "channel group sparisy/flood",
        "sim_hook": "channel-group bitmap density and group-skip scheduling",
        "default_policy": "requires_bitmap_decode_and_group_skip_validation",
    },
]

TRACKED_SUFFIXES = {
    ".v",
    ".sv",
    ".vh",
    ".scala",
    ".sbt",
    ".c",
    ".h",
    ".py",
    ".md",
    ".txt",
    ".csv",
}


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def interesting(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if any(part in parts for part in {".git", "target", "test_run_dir", ".bloop", ".metals", ".bsp"}):
        return False
    return path.suffix.lower() in TRACKED_SUFFIXES


def files_by_rel(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    out: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and interesting(path.relative_to(root)):
            out[str(path.relative_to(root)).replace("\\", "/")] = path
    return out


def classify(rel: str) -> str:
    lower = rel.lower()
    if "/rtl/" in f"/{lower}" or lower.startswith("rtl/") or lower.endswith((".v", ".sv", ".vh")):
        return "rtl"
    if lower.startswith("tb/") or "/tb/" in lower or "test" in lower:
        return "testbench_or_test"
    if lower.endswith((".md", ".txt")) or "/doc/" in lower:
        return "docs"
    if lower.endswith((".c", ".h", ".py", ".scala", ".sbt")):
        return "software_or_generator"
    if lower.endswith(".csv"):
        return "data"
    return "other"


def key_signal_hits(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")[:200_000]
    keywords = [
        "softmax",
        "outlier",
        "zero",
        "skip",
        "spars",
        "bitmap",
        "int4",
        "int8",
        "precision",
        "mactree",
        "group",
    ]
    hits = sorted({kw for kw in keywords if kw.lower() in text.lower()})
    return ";".join(hits)


def build_inventory(base_root: Path, out_dir: Path) -> None:
    base = files_by_rel(base_root)
    details: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for spec in MECHANISMS:
        mech = spec["mechanism"]
        root = Path(spec["root"])
        candidate = files_by_rel(root)
        changed = 0
        added = 0
        removed = 0
        category_counts: dict[str, int] = {}

        for rel, path in sorted(candidate.items()):
            base_path = base.get(rel)
            if base_path is None:
                status = "added"
                added += 1
            else:
                status = "same" if sha1(path) == sha1(base_path) else "modified"
                if status == "same":
                    continue
                changed += 1
            category = classify(rel)
            category_counts[category] = category_counts.get(category, 0) + 1
            details.append(
                {
                    "mechanism": mech,
                    "file_status": status,
                    "category": category,
                    "relative_path": rel,
                    "source_path": str(path),
                    "base_path": str(base_path or ""),
                    "bytes": path.stat().st_size,
                    "keyword_hits": key_signal_hits(path) if path.suffix.lower() in {".v", ".sv", ".vh", ".scala", ".md", ".py", ".c", ".h"} else "",
                    "sim_hook": spec["sim_hook"],
                    "paper_use_policy": spec["default_policy"],
                }
            )

        for rel, base_path in sorted(base.items()):
            if rel not in candidate:
                removed += 1

        summary.append(
            {
                "mechanism": mech,
                "source_root": spec["root"],
                "changed_or_added_files": changed + added,
                "modified_files": changed,
                "added_files": added,
                "removed_vs_base_files": removed,
                "rtl_files": category_counts.get("rtl", 0),
                "testbench_or_test_files": category_counts.get("testbench_or_test", 0),
                "docs_files": category_counts.get("docs", 0),
                "software_or_generator_files": category_counts.get("software_or_generator", 0),
                "data_files": category_counts.get("data", 0),
                "sim_hook": spec["sim_hook"],
                "integration_status": "inventory_only_not_integrated",
                "paper_use_policy": spec["default_policy"],
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "mechanism_changed_files.csv", details)
    write_csv(out_dir / "mechanism_summary.csv", summary)
    write_csv(
        out_dir / "mechanism_sim_hooks.csv",
        [
            {
                "mechanism": spec["mechanism"],
                "sim_hook": spec["sim_hook"],
                "required_inputs": required_inputs(spec["mechanism"]),
                "minimum_evidence_to_enable": spec["default_policy"],
                "current_default": "disabled",
            }
            for spec in MECHANISMS
        ],
    )
    write_csv(
        out_dir / "mechanism_enable_template.csv",
        [
            {
                "mechanism": spec["mechanism"],
                "enabled": "false",
                "evidence_status": "missing",
                "timing_evidence_csv": "",
                "value_evidence_csv": "",
                "quality_evidence_csv": "",
                "workload_scope": "",
                "sim_hook": spec["sim_hook"],
                "paper_use_policy": "do_not_enable_until_evidence_passes",
                "notes": f"Required: {required_inputs(spec['mechanism'])}",
            }
            for spec in MECHANISMS
        ],
    )
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                "# FLOOD mechanism inventory",
                "",
                "This inventory compares the six standalone optimization folders against `FLOOD/`.",
                "",
                "The result is not an integration patch. It is a gate for simulator work:",
                "",
                "- `mechanism_summary.csv`: per-mechanism changed-file counts and simulator hook.",
                "- `mechanism_changed_files.csv`: changed or added files relative to base.",
                "- `mechanism_sim_hooks.csv`: required simulator inputs and evidence gate.",
                "- `mechanism_enable_template.csv`: explicit disabled-by-default mechanism switch template.",
                "",
                "Paper policy: all mechanisms remain disabled in main simulator results until RTL timing and output-value evidence is available for the claimed scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def required_inputs(mechanism: str) -> str:
    return {
        "mactree": "rtl cycle traces; MAC output values; activity counters if power is claimed",
        "outlier": "outlier ratio per layer; golden/RTL output values; route-shift timing",
        "INT8-INT4": "precision mode per layer; packed data width; value tolerance; RTL timing",
        "softmax": "vector dimension; softmax input/output values; module done cycles",
        "zero-skip": "activation/weight zero ratio; skip counters; RTL timing and values",
        "channel_group_sparsity": "bitmap density per channel group; decode cycles; group-skip counters",
    }[mechanism]


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-root", default="FLOOD")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/mechanism_inventory")
    args = parser.parse_args()
    build_inventory(Path(args.base_root), Path(args.out_dir))
    print(f"wrote mechanism inventory to {args.out_dir}")


if __name__ == "__main__":
    main()
