#!/usr/bin/env python3
"""Generate simple 256-bit hex files for FLOOD RTL smoke calibration."""
from __future__ import annotations

import argparse
from pathlib import Path


def line256(seed: int) -> str:
    vals = [((seed + i + 1) & 0xFF) for i in range(32)]
    packed = sum(v << (8 * i) for i, v in enumerate(vals))
    return "{:064x}\n".format(packed)


def line_multi256(seed: int, chunks: int) -> str:
    words = []
    for chunk in range(chunks):
        vals = [((seed + chunk * 37 + i + 1) & 0xFF) for i in range(32)]
        packed = sum(v << (8 * i) for i, v in enumerate(vals))
        words.append("{:064x}".format(packed))
    return "".join(reversed(words)) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--k", type=int, required=True)
    p.add_argument("--cout", type=int, required=True)
    p.add_argument("--group-size", type=int, required=True)
    p.add_argument("--group-num", type=int, required=True)
    p.add_argument("--cin-idx-total", type=int, required=True)
    p.add_argument("--res-cols", type=int, required=True)
    p.add_argument("--res-rows", type=int, required=True)
    p.add_argument("--row-size", type=int, default=32)
    p.add_argument("--col-size", type=int, default=32)
    args = p.parse_args()

    weight_lines = args.cout * args.cin_idx_total * args.k * args.k * args.group_size
    feature_lines = (args.group_num * args.res_rows) * (args.cin_idx_total * args.row_size * args.group_size)

    Path("weights_ping.hex").write_text("".join(line256(i) for i in range(weight_lines)), encoding="ascii")
    Path("features.hex").write_text(
        "".join(line_multi256(i * 3, args.res_cols) for i in range(feature_lines)),
        encoding="ascii",
    )
    print("weights_ping.hex lines={}".format(weight_lines))
    print("features.hex lines={}".format(feature_lines))


if __name__ == "__main__":
    main()
