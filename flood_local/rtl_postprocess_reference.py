#!/usr/bin/env python3
"""Small software reference slices for FLOOD OutRouterPlanePost.

This is intentionally narrow. It models the address/write and arithmetic
semantics needed by the first independent golden checks, not every work mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rtl_math_reference import dynamic_truncate_signed, wrap_signed


Vector = list[int]
Write = tuple[str, int, Vector]


@dataclass(frozen=True)
class PlanePostConfig:
    k: int
    group_num: int
    cout: int
    col_size: int = 32
    work_mode: int = 0
    col_idx: int = 0
    max_resolution_col: int = 32
    max_kernel_block_cout: int = 512
    max_group_num: int = 16
    output_tmp_width: int = 16
    output_data_width: int = 8
    source_width: int = 30
    truncate_en: bool = False
    truncate_bits: int = 0


@dataclass(frozen=True)
class PlanePostEvent:
    data: Vector
    feature_map_line: int
    kernel_row: int
    count: int
    cout: int


@dataclass
class PlanePostState:
    output_sram: dict[int, Vector] = field(default_factory=dict)
    joint_sram: dict[int, Vector] = field(default_factory=dict)


def static_truncate_to_signed(value: int, *, source_width: int, output_width: int) -> int:
    """Match OutRouterPlanePost.truncateData when truncateBits=0."""
    del source_width
    maximum = (1 << (output_width - 1)) - 1
    minimum = -(1 << (output_width - 1))
    return max(minimum, min(maximum, value))


def _zero_vec(col_size: int) -> Vector:
    return [0] * col_size


def _checked_vec(vec: Vector, col_size: int) -> Vector:
    if len(vec) != col_size:
        raise ValueError(f"expected vector length {col_size}, got {len(vec)}")
    return list(vec)


def _add_vecs(*vecs: Vector, width: int) -> Vector:
    if not vecs:
        return []
    return [wrap_signed(sum(vec[i] for vec in vecs), width) for i in range(len(vecs[0]))]


def _addresses(config: PlanePostConfig, event: PlanePostEvent) -> dict[str, int | bool]:
    position = event.feature_map_line + (config.k - event.kernel_row)
    output_write_en = position <= config.group_num
    joint_write_en = position > config.group_num
    output_base = event.cout * (config.group_num + 1)
    joint_base = config.col_idx * (config.cout + 1) * config.k + event.cout * config.k
    output_buffer_bias = config.max_kernel_block_cout * config.max_group_num
    joint_buffer_bias = (config.max_resolution_col // config.col_size + 1) * (config.cout + 1) * config.k
    count_bias = 0 if event.count == 0 else output_buffer_bias
    joint_count_bias = 0 if event.count == 0 else joint_buffer_bias

    output_write_addr = output_base + position + count_bias if output_write_en else 0
    joint_write_addr = joint_base + (position - config.group_num - 1) + joint_count_bias if joint_write_en else 0

    output_read_addr = output_write_addr
    joint_height_read_addr = joint_write_addr
    joint_width_read_addr = (
        joint_base + (position - config.group_num - 1) + joint_buffer_bias - (config.cout + 1) * config.k
        if joint_write_en and event.count == 0
        else 0
    )
    return {
        "position": position,
        "output_write_en": output_write_en,
        "joint_write_en": joint_write_en,
        "output_write_addr": output_write_addr,
        "joint_write_addr": joint_write_addr,
        "output_read_addr": output_read_addr,
        "joint_height_read_addr": joint_height_read_addr,
        "joint_width_read_addr": joint_width_read_addr,
    }


def apply_plane_post_event(state: PlanePostState, event: PlanePostEvent, config: PlanePostConfig) -> list[Write]:
    """Apply one isolated OutRouterPlanePost input event.

    Covered now:
    - workMode 0 direct output/joint writes.
    - workMode 3 input-channel accumulation at the same output/joint address.
    """
    current = [
        static_truncate_to_signed(value, source_width=config.source_width, output_width=config.output_tmp_width)
        for value in _checked_vec(event.data, config.col_size)
    ]
    addresses = _addresses(config, event)
    output_write_en = bool(addresses["output_write_en"])
    joint_write_en = bool(addresses["joint_write_en"])
    output_addr = int(addresses["output_write_addr"])
    joint_addr = int(addresses["joint_write_addr"])

    if config.work_mode == 0:
        merged = current
    elif config.work_mode == 3:
        if output_write_en:
            prior = state.output_sram.get(output_addr, _zero_vec(config.col_size))
        else:
            prior = state.joint_sram.get(joint_addr, _zero_vec(config.col_size))
        merged = _add_vecs(current, prior, width=config.output_tmp_width)
    else:
        raise NotImplementedError(f"work_mode {config.work_mode} is not implemented in the Python reference yet")

    if event.count == 0 and output_write_en:
        merged = [
            dynamic_truncate_signed(
                value,
                truncate_bits=config.truncate_bits,
                enabled=config.truncate_en,
                output_width=config.output_data_width,
            )
            for value in merged
        ]
        merged = [wrap_signed(value, config.output_tmp_width) for value in merged]

    writes: list[Write] = []
    if output_write_en:
        state.output_sram[output_addr] = list(merged)
        writes.append(("output", output_addr, list(merged)))
    if joint_write_en:
        state.joint_sram[joint_addr] = list(merged)
        writes.append(("joint", joint_addr, list(merged)))
    return writes


wrap_signed = wrap_signed
