#!/usr/bin/env python3
"""Build and verify a minimal RTL/source bundle for server reproduction."""

from __future__ import annotations

import argparse
import csv
import hashlib
import tarfile
from pathlib import Path


SOURCE_PATHS = [
    "FLOOD/src/main/scala/Machine",
    "FLOOD/src/main/scala/core",
    "FLOOD/src/main/scala/sram",
    "FLOOD/src/main/scala/IO",
    "FLOOD/rtl/e203/subsys/mac_unit",
    "FLOOD/rtl/e203/subsys/dma",
    "FLOOD/rtl/e203/subsys/e203_subsys_top.v",
    "FLOOD/rtl/e203/subsys/e203_subsys_nice_core.v",
    "FLOOD/rtl/e203/subsys/bus/top/bus_top.v",
    "FLOOD/rtl/e203/core/e203_exu_nice.v",
    "FLOOD/rtl/e203/core/e203_lsu*.v",
    "FLOOD/rtl/e203/core/e203_biu.v",
    "FLOOD/rtl/e203/core/e203_cpu_top.v",
    "FLOOD/tb",
    "FLOOD/src/test/scala/machine",
    "FLOOD/src/test/scala/core",
    "mactree/flood/src/main/scala/core",
    "outlier/flood/src/main/scala/core",
    "outlier/flood/src/main/scala/Machine",
    "outlier/flood/src/python",
    "outlier/flood/src/tmp",
    "INT8-INT4/flood/src/main/scala/core",
    "INT8-INT4/flood/src/main/scala/Machine",
    "INT8-INT4/flood/src/python",
    "INT8-INT4/flood/src/tmp",
    "zero-skip/flood/src/main/scala/core",
    "zero-skip/flood/src/main/scala/Machine",
    "channel group sparisy/flood/src/main/scala/core",
    "channel group sparisy/flood/src/main/scala/Machine",
]

ALLOWED_SUFFIXES = {".scala", ".v", ".sv", ".vh", ".md", ".py", ".txt", ".csv", ".sbt", ".c", ".h"}


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


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def iter_bundle_files(root: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    missing: list[str] = []
    for raw in SOURCE_PATHS:
        matches = sorted(root.glob(raw))
        if not matches:
            missing.append(raw)
            continue
        for path in matches:
            if path.is_file():
                if path.suffix in ALLOWED_SUFFIXES:
                    files.append(path)
                continue
            for child in path.rglob("*"):
                if child.is_file() and child.suffix in ALLOWED_SUFFIXES:
                    files.append(child)
    unique = sorted(set(files), key=lambda p: p.relative_to(root).as_posix())
    return unique, missing


def manifest_rows(root: Path, files: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        rows.append(
            {
                "relative_path": rel,
                "bytes": str(path.stat().st_size),
                "sha256": sha256_file(path),
            }
        )
    return rows


def bundle_signature(rows: list[dict[str, str]]) -> str:
    payload = "\n".join(f"{row['relative_path']}|{row['bytes']}|{row['sha256']}" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_bundle(root: Path, out_dir: Path, archive: Path) -> None:
    files, missing = iter_bundle_files(root)
    rows = manifest_rows(root, files)
    signature = bundle_signature(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "rtl_source_bundle_manifest.csv"
    write_csv(manifest, rows)
    summary = [
        {
            "bundle_status": "pass" if files and not missing else "missing_sources",
            "source_files": str(len(files)),
            "missing_source_paths": str(len(missing)),
            "missing_path_names": ";".join(missing),
            "bundle_signature_sha256": signature,
            "archive_path": str(archive),
            "policy": "Use this bundle only to reproduce postprocessor/source-profile gates on a server system disk.",
        }
    ]
    write_csv(out_dir / "rtl_source_bundle_summary.csv", summary)
    (out_dir / "rtl_source_bundle_signature.txt").write_text(signature + "\n", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tar:
        for path in files:
            tar.add(path, arcname=path.relative_to(root).as_posix())
        tar.add(manifest, arcname="results/flood_cycle_sim_v1/source_bundle/rtl_source_bundle_manifest.csv")
        tar.add(out_dir / "rtl_source_bundle_summary.csv", arcname="results/flood_cycle_sim_v1/source_bundle/rtl_source_bundle_summary.csv")
        tar.add(out_dir / "rtl_source_bundle_signature.txt", arcname="results/flood_cycle_sim_v1/source_bundle/rtl_source_bundle_signature.txt")
    readme = f"""# FLOOD RTL Source Bundle

This directory describes the minimal source bundle used to reproduce
postprocessor source-profile gates on a Linux server.

Archive: `{archive}`

The archive is intentionally not the full RTL repository. It includes only the
files read by current source-manifest and mechanism-profile scripts. It is not
enough to claim full RTL simulation completeness.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    if missing:
        raise SystemExit(f"Missing {len(missing)} source path(s). See rtl_source_bundle_summary.csv.")


def verify_bundle(root: Path, manifest: Path, out_dir: Path) -> None:
    expected = read_rows(manifest)
    rows: list[dict[str, str]] = []
    for row in expected:
        rel = row["relative_path"]
        path = root / rel
        if not path.exists():
            rows.append({"relative_path": rel, "status": "missing", "expected_sha256": row["sha256"], "actual_sha256": "", "expected_bytes": row["bytes"], "actual_bytes": "0"})
            continue
        actual_hash = sha256_file(path)
        actual_bytes = str(path.stat().st_size)
        ok = actual_hash == row["sha256"] and actual_bytes == row["bytes"]
        rows.append(
            {
                "relative_path": rel,
                "status": "pass" if ok else "mismatch",
                "expected_sha256": row["sha256"],
                "actual_sha256": actual_hash,
                "expected_bytes": row["bytes"],
                "actual_bytes": actual_bytes,
            }
        )
    failures = [row for row in rows if row["status"] != "pass"]
    write_csv(out_dir / "rtl_source_bundle_verify.csv", rows)
    expected_sig = bundle_signature(expected)
    actual_manifest_rows = [
        {"relative_path": row["relative_path"], "bytes": row["actual_bytes"], "sha256": row["actual_sha256"]}
        for row in rows
        if row["status"] == "pass"
    ]
    actual_sig = bundle_signature(actual_manifest_rows) if not failures else ""
    write_csv(
        out_dir / "rtl_source_bundle_verify_summary.csv",
        [
            {
                "verify_status": "pass" if not failures else "fail",
                "checked_files": str(len(rows)),
                "failed_files": str(len(failures)),
                "expected_bundle_signature_sha256": expected_sig,
                "actual_bundle_signature_sha256": actual_sig,
                "policy": "Server source bundle must verify before running postprocessor source-profile gates.",
            }
        ],
    )
    if failures:
        raise SystemExit(f"Source bundle verification failed for {len(failures)} file(s).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-dir", default="results/flood_cycle_sim_v1/source_bundle")
    parser.add_argument("--archive", default="results/flood_cycle_sim_v1/source_bundle/rtl_source_bundle.tar.gz")
    parser.add_argument("--verify-root", default="")
    parser.add_argument("--manifest", default="")
    args = parser.parse_args()
    if args.verify_root:
        if not args.manifest:
            raise SystemExit("--manifest is required with --verify-root")
        verify_bundle(Path(args.verify_root), Path(args.manifest), Path(args.out_dir))
    else:
        build_bundle(Path(args.root), Path(args.out_dir), Path(args.archive))


if __name__ == "__main__":
    main()
