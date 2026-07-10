#!/usr/bin/env python3
"""Bit-level arithmetic primitives extracted from FLOOD RTL/Chisel sources."""

from __future__ import annotations


def signed_from_bits(value: int, width: int) -> int:
    """Interpret the low ``width`` bits as a two's-complement signed integer."""
    if width <= 0:
        raise ValueError("width must be positive")
    mask = (1 << width) - 1
    value &= mask
    sign = 1 << (width - 1)
    return value - (1 << width) if value & sign else value


def wrap_signed(value: int, width: int) -> int:
    """Wrap an integer through a fixed-width Chisel SInt assignment."""
    return signed_from_bits(value, width)


def mac_tree_dot(lhs_bits: list[int], rhs_bits: list[int], data_width: int = 8) -> int:
    """Reference the signed multiply-and-reduce behavior of one MACTree column."""
    if len(lhs_bits) != len(rhs_bits):
        raise ValueError("MAC vectors must have the same length")
    return sum(signed_from_bits(lhs, data_width) * signed_from_bits(rhs, data_width) for lhs, rhs in zip(lhs_bits, rhs_bits))


def dynamic_truncate_signed(value: int, *, truncate_bits: int, enabled: bool, output_width: int) -> int:
    """Match DynamicTruncateData: arithmetic shift, bit-based round-up, saturation."""
    if truncate_bits < 0:
        raise ValueError("truncate_bits must not be negative")
    if output_width <= 0:
        raise ValueError("output_width must be positive")

    shifted = value >> truncate_bits if truncate_bits else value
    if not enabled:
        return shifted

    if truncate_bits and ((value >> (truncate_bits - 1)) & 1):
        shifted += 1

    maximum = (1 << (output_width - 1)) - 1
    minimum = -(1 << (output_width - 1))
    return max(minimum, min(maximum, shifted))
