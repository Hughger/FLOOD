#!/usr/bin/env python3
"""Smoke tests for RTL hex decoding and feature address mapping."""

from __future__ import annotations

from rtl_hex_mapping import feature_read_addresses, split_hex_line_to_u8_chunks


def pack_chunk(seed: int) -> str:
    vals = [((seed + i + 1) & 0xFF) for i in range(32)]
    packed = sum(v << (8 * i) for i, v in enumerate(vals))
    return f"{packed:064x}"


def test_split_hex_line_returns_chunks_in_verilog_slice_order() -> None:
    line = pack_chunk(37) + pack_chunk(0)
    chunks = split_hex_line_to_u8_chunks(line, chunk_bytes=32)
    assert chunks[0][:4] == [1, 2, 3, 4]
    assert chunks[1][:4] == [38, 39, 40, 41]


def test_feature_read_addresses_match_testbench_formula() -> None:
    rows = feature_read_addresses(
        cin_idx=1,
        resolution_col_idx=0,
        resolution_row_idx=1,
        row_size=4,
        tile_size=4,
        group_size=2,
        group_num=2,
        resolution_row_idx_total=3,
    )
    assert rows[0] == {"tile_id": 0, "row": 0, "addr_in_hex": 74, "resolution_col_idx": 0}
    assert rows[1] == {"tile_id": 0, "row": 1, "addr_in_hex": 80, "resolution_col_idx": 0}
    assert rows[4] == {"tile_id": 1, "row": 0, "addr_in_hex": 50, "resolution_col_idx": 0}


if __name__ == "__main__":
    test_split_hex_line_returns_chunks_in_verilog_slice_order()
    test_feature_read_addresses_match_testbench_formula()
    print("RTL hex mapping smoke test passed")
