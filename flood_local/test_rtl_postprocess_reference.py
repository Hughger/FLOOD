#!/usr/bin/env python3
"""Tests for the OutRouterPlanePost software reference slices."""

from __future__ import annotations

from rtl_postprocess_reference import (
    PlanePostConfig,
    PlanePostEvent,
    PlanePostState,
    apply_plane_post_event,
    static_truncate_to_signed,
    wrap_signed,
)


def test_wrap_signed_matches_chisel_sint_assignment_width() -> None:
    assert wrap_signed(32767, 16) == 32767
    assert wrap_signed(32768, 16) == -32768
    assert wrap_signed(-32769, 16) == 32767


def test_static_truncate_saturates_output_noc_values_to_tmp_width() -> None:
    assert static_truncate_to_signed(123, source_width=30, output_width=16) == 123
    assert static_truncate_to_signed(40000, source_width=30, output_width=16) == 32767
    assert static_truncate_to_signed(-40000, source_width=30, output_width=16) == -32768


def test_work_mode_0_direct_output_write_uses_output_address_and_packs_values() -> None:
    state = PlanePostState()
    event = PlanePostEvent(
        data=[1, -2, 40000, -40000],
        feature_map_line=0,
        kernel_row=1,
        count=0,
        cout=2,
    )
    writes = apply_plane_post_event(
        state,
        event,
        PlanePostConfig(k=1, group_num=1, cout=3, col_size=4, max_kernel_block_cout=8, max_group_num=4),
    )

    assert writes == [("output", 2 * (1 + 1) + 0, [1, -2, 32767, -32768])]
    assert state.output_sram[4] == [1, -2, 32767, -32768]
    assert state.joint_sram == {}


def test_work_mode_3_accumulates_existing_output_row_for_input_channel_fill() -> None:
    state = PlanePostState(output_sram={1: [10, -10, 32760, -32760]})
    event = PlanePostEvent(
        data=[5, -5, 20, -20],
        feature_map_line=0,
        kernel_row=0,
        count=0,
        cout=0,
    )

    writes = apply_plane_post_event(
        state,
        event,
        PlanePostConfig(k=1, group_num=1, cout=1, col_size=4, max_kernel_block_cout=8, max_group_num=4, work_mode=3),
    )

    assert writes == [("output", 1, [15, -15, -32756, 32756])]
    assert state.output_sram[1] == [15, -15, -32756, 32756]


if __name__ == "__main__":
    test_wrap_signed_matches_chisel_sint_assignment_width()
    test_static_truncate_saturates_output_noc_values_to_tmp_width()
    test_work_mode_0_direct_output_write_uses_output_address_and_packs_values()
    test_work_mode_3_accumulates_existing_output_row_for_input_channel_fill()
    print("RTL postprocess reference smoke test passed")
