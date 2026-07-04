#!/usr/bin/env python3
"""Generate deterministic numerical microbenchmarks for E3/E4/E5 proxy tables."""
from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path
from typing import Any


SEED = 20260704


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def mse(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) / max(1, len(a))


def max_abs(a: list[float], b: list[float]) -> float:
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def quantize_symmetric(values: list[float], bits: int) -> list[float]:
    qmax = (1 << (bits - 1)) - 1
    scale = max(abs(v) for v in values) / qmax if values else 1.0
    if scale == 0:
        return [0.0 for _ in values]
    return [max(-qmax, min(qmax, round(v / scale))) * scale for v in values]


def softmax(values: list[float]) -> list[float]:
    peak = max(values)
    exps = [math.exp(v - peak) for v in values]
    total = sum(exps)
    return [v / total for v in exps]


def softmax_int8_lut_proxy(values: list[float]) -> list[float]:
    clipped = [max(-8.0, min(8.0, v)) for v in values]
    q = quantize_symmetric(clipped, 8)
    return softmax(q)


def softmax_piecewise_proxy(values: list[float]) -> list[float]:
    peak = max(values)
    approx = []
    for value in values:
        x = max(-8.0, min(0.0, value - peak))
        approx.append(max(0.0, 1.0 + x / 8.0) ** 2)
    total = sum(approx)
    return [v / total for v in approx] if total else [1.0 / len(values) for _ in values]


def softmax_streaming_proxy(values: list[float]) -> list[float]:
    return softmax([round(v, 3) for v in values])


def build_rows(samples: int) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    rows: list[dict[str, Any]] = []
    vector_lengths = [32, 64, 128, 256, 512, 1024, 2048]

    for bits, config in [(8, "INT8 all"), (4, "INT4 all"), (4, "30% INT4 mixed"), (4, "sensitivity-based mixed")]:
        values = [rng.gauss(0.0, 1.0) for _ in range(samples)]
        if "mixed" in config:
            head = int(len(values) * 0.30)
            quantized = quantize_symmetric(values[:head], bits) + quantize_symmetric(values[head:], 8)
        elif "sensitivity" in config:
            keep = int(len(values) * 0.20)
            quantized = values[:keep] + quantize_symmetric(values[keep:], bits)
        else:
            quantized = quantize_symmetric(values, bits)
        rows.append(
            {
                "experiment": "E3_quantization",
                "config": config,
                "vector_length": samples,
                "mse": round(mse(values, quantized), 10),
                "max_abs_error": round(max_abs(values, quantized), 10),
                "cosine_similarity": round(cosine(values, quantized), 10),
                "source": "deterministic synthetic tensor microbench",
            }
        )

    values = [rng.gauss(0.0, 1.0) for _ in range(samples)]
    sorted_idx = sorted(range(len(values)), key=lambda i: abs(values[i]), reverse=True)
    for ratio, config in [(0.0, "INT8 truncation"), (0.001, "+ outlier bypass 0.1%"), (0.005, "+ outlier bypass 0.5%"), (0.010, "+ outlier bypass 1.0%")]:
        bypass_count = max(0, int(len(values) * ratio))
        bypass = set(sorted_idx[:bypass_count])
        q_values = quantize_symmetric(values, 8)
        recovered = [values[i] if i in bypass else q_values[i] for i in range(len(values))]
        rows.append(
            {
                "experiment": "E4_outlier",
                "config": config,
                "vector_length": samples,
                "mse": round(mse(values, recovered), 10),
                "max_abs_error": round(max_abs(values, recovered), 10),
                "cosine_similarity": round(cosine(values, recovered), 10),
                "source": "deterministic synthetic tensor microbench",
            }
        )

    softmax_impls = [
        ("FP32 reference softmax", softmax),
        ("INT8 LUT softmax proxy", softmax_int8_lut_proxy),
        ("piecewise-linear softmax proxy", softmax_piecewise_proxy),
        ("online/streaming softmax proxy", softmax_streaming_proxy),
    ]
    for length in vector_lengths:
        values = [rng.gauss(0.0, 1.0) for _ in range(length)]
        reference = softmax(values)
        for config, fn in softmax_impls:
            approx = fn(values)
            rows.append(
                {
                    "experiment": "E5_softmax",
                    "config": config,
                    "vector_length": length,
                    "mse": round(mse(reference, approx), 12),
                    "max_abs_error": round(max_abs(reference, approx), 12),
                    "cosine_similarity": round(cosine(reference, approx), 10),
                    "source": "deterministic synthetic tensor microbench",
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--samples", type=int, default=4096)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    rows = build_rows(args.samples)
    write_csv(out_dir / "quant_outlier_softmax_quality.csv", rows)
    print(f"wrote numerical quality microbench to {out_dir}")


if __name__ == "__main__":
    main()
