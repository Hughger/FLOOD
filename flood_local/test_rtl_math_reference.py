#!/usr/bin/env python3
"""Tests for bit-exact FLOOD RTL arithmetic primitives."""

from __future__ import annotations

from rtl_math_reference import dynamic_truncate_signed, mac_tree_dot, signed_from_bits


def test_signed_from_bits_uses_twos_complement() -> None:
    assert signed_from_bits(0x7F, 8) == 127
    assert signed_from_bits(0x80, 8) == -128
    assert signed_from_bits(0xFF, 8) == -1


def test_mac_tree_dot_matches_signed_8bit_products() -> None:
    assert mac_tree_dot([0x01, 0xFF], [0x02, 0x03]) == -1
    assert mac_tree_dot([0x80, 0x7F], [0x80, 0x7F]) == 32513


def test_dynamic_truncate_matches_rtl_rounding_and_saturation() -> None:
    assert dynamic_truncate_signed(7, truncate_bits=1, enabled=True, output_width=8) == 4
    assert dynamic_truncate_signed(6, truncate_bits=1, enabled=True, output_width=8) == 3
    assert dynamic_truncate_signed(-3, truncate_bits=1, enabled=True, output_width=8) == -1
    assert dynamic_truncate_signed(400, truncate_bits=0, enabled=True, output_width=8) == 127
    assert dynamic_truncate_signed(-200, truncate_bits=0, enabled=True, output_width=8) == -128
    assert dynamic_truncate_signed(7, truncate_bits=1, enabled=False, output_width=8) == 3


if __name__ == "__main__":
    test_signed_from_bits_uses_twos_complement()
    test_mac_tree_dot_matches_signed_8bit_products()
    test_dynamic_truncate_matches_rtl_rounding_and_saturation()
    print("RTL math reference smoke test passed")
