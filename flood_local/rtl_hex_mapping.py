#!/usr/bin/env python3
"""Helpers for matching FLOOD RTL testbench hex packing and feature reads."""

from __future__ import annotations


def split_hex_line_to_u8_chunks(hex_line: str, chunk_bytes: int = 32) -> list[list[int]]:
    """Split one readmemh line into low-to-high Verilog `+:` chunks of u8 values."""
    clean = hex_line.strip().replace("_", "")
    if not clean:
        return []
    value = int(clean, 16)
    total_bytes = len(clean) // 2
    if total_bytes % chunk_bytes != 0:
        raise ValueError(f"hex line has {total_bytes} bytes, not a multiple of {chunk_bytes}")
    chunks: list[list[int]] = []
    for chunk in range(total_bytes // chunk_bytes):
        base = chunk * chunk_bytes
        chunks.append([(value >> (8 * (base + i))) & 0xFF for i in range(chunk_bytes)])
    return chunks


def feature_read_addresses(
    *,
    cin_idx: int,
    resolution_col_idx: int,
    resolution_row_idx: int,
    row_size: int,
    tile_size: int,
    group_size: int,
    group_num: int,
    resolution_row_idx_total: int,
) -> list[dict[str, int]]:
    """Return the feature hex addresses driven by `drive_feature_from_files`."""
    rows: list[dict[str, int]] = []
    for tile_id in range(tile_size):
        start_row_cin = (
            cin_idx * (row_size * group_size)
            + ((group_size - 1 - (tile_id % group_size)) * row_size)
        ) * (group_num * resolution_row_idx_total)
        start_row_height = (resolution_row_idx * group_num) + (tile_id // group_size)
        start_row = start_row_cin + start_row_height
        for row in range(row_size):
            rows.append(
                {
                    "tile_id": tile_id,
                    "row": row,
                    "addr_in_hex": start_row + row * group_num * resolution_row_idx_total,
                    "resolution_col_idx": resolution_col_idx,
                }
            )
    return rows
