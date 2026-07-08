#!/usr/bin/env python3
"""Smoke test for RTL calibration hex packing."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


PYTHON = r"C:\Users\98676\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
SCRIPT = Path("results/flood_pytorchsim_backend_v1/rtl_calibration_src/make_simple_hex.py").resolve()


def test_features_hex_packs_all_resolution_columns_into_each_memory_row() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        subprocess.run(
            [
                PYTHON,
                str(SCRIPT),
                "--k",
                "3",
                "--cout",
                "2",
                "--group-size",
                "4",
                "--group-num",
                "4",
                "--cin-idx-total",
                "2",
                "--res-cols",
                "2",
                "--res-rows",
                "2",
            ],
            cwd=work,
            check=True,
            text=True,
            capture_output=True,
        )
        first_feature_line = (work / "features.hex").read_text(encoding="ascii").splitlines()[0]
        assert len(first_feature_line) == 128


if __name__ == "__main__":
    test_features_hex_packs_all_resolution_columns_into_each_memory_row()
    print("make_simple_hex packing smoke test passed")
