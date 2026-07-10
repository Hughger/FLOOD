#!/usr/bin/env python3
"""Regression check for Chisel 3.6 source syntax used by RTL calibration."""

from __future__ import annotations

from pathlib import Path


RTL_SCALA_ROOT = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "flood_pytorchsim_backend_v1"
    / "rtl_calibration_src"
    / "src"
)


def test_chisel_zero_argument_methods_have_no_empty_argument_list() -> None:
    forbidden = (".asUInt()", ".asSInt()", ".orR()")
    offenders = [
        f"{path.relative_to(RTL_SCALA_ROOT).as_posix()}: {token}"
        for path in RTL_SCALA_ROOT.rglob("*.scala")
        for token in forbidden
        if token in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"Chisel 3.6 requires parameterless API syntax: {offenders}"


if __name__ == "__main__":
    test_chisel_zero_argument_methods_have_no_empty_argument_list()
    print("Chisel source compatibility test passed")
