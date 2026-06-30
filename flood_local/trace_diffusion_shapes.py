#!/usr/bin/env python3
"""Trace Conv2d and Linear shapes from a Diffusion model forward pass.

This script is intentionally dependency-light except for torch/diffusers. It does
not validate image quality; it only records operator shapes for PyTorchSim tests.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

try:
    import torch
except ModuleNotFoundError:  # Allows --help on machines without PyTorch.
    torch = None


@dataclass
class OpShape:
    op_id: str
    module_name: str
    operator: str
    batch: int
    h_or_m: int
    w_or_k: int
    in_channels_or_features: int
    out_channels_or_features: int
    kernel: int
    stride: int
    padding: int
    pytorchsim_shape_args: str
    note: str


def tensor_shape(x: Any) -> tuple[int, ...] | None:
    if torch is None:
        return None
    if isinstance(x, torch.Tensor):
        return tuple(int(v) for v in x.shape)
    if isinstance(x, (list, tuple)) and x and isinstance(x[0], torch.Tensor):
        return tuple(int(v) for v in x[0].shape)
    return None


def register_hooks(model: torch.nn.Module, rows: list[OpShape]) -> list[Any]:
    if torch is None:
        raise RuntimeError("PyTorch is required to trace model shapes.")
    hooks = []

    def add_hook(name: str, module: torch.nn.Module):
        def hook(mod: torch.nn.Module, inputs: tuple[Any, ...], output: Any):
            shape = tensor_shape(inputs[0] if inputs else None)
            if shape is None:
                return
            op_index = len(rows)
            if isinstance(mod, torch.nn.Conv2d) and len(shape) == 4:
                b, cin, h, w = shape
                kernel = mod.kernel_size[0] if isinstance(mod.kernel_size, tuple) else int(mod.kernel_size)
                stride = mod.stride[0] if isinstance(mod.stride, tuple) else int(mod.stride)
                padding = mod.padding[0] if isinstance(mod.padding, tuple) else int(mod.padding)
                rows.append(
                    OpShape(
                        op_id=f"op_{op_index:05d}",
                        module_name=name,
                        operator="conv",
                        batch=b,
                        h_or_m=h,
                        w_or_k=w,
                        in_channels_or_features=cin,
                        out_channels_or_features=int(mod.out_channels),
                        kernel=kernel,
                        stride=stride,
                        padding=padding,
                        pytorchsim_shape_args=f"{b} {h} {w} {cin} {int(mod.out_channels)} {kernel} {stride} {padding}",
                        note="Conv2d input is NCHW; PyTorchSim conv expects B H W I_C O_C K S P.",
                    )
                )
            elif isinstance(mod, torch.nn.Linear):
                in_features = int(mod.in_features)
                out_features = int(mod.out_features)
                if len(shape) == 2:
                    m = shape[0]
                else:
                    m = 1
                    for v in shape[:-1]:
                        m *= v
                rows.append(
                    OpShape(
                        op_id=f"op_{op_index:05d}",
                        module_name=name,
                        operator="gemm",
                        batch=shape[0],
                        h_or_m=int(m),
                        w_or_k=in_features,
                        in_channels_or_features=in_features,
                        out_channels_or_features=out_features,
                        kernel=1,
                        stride=1,
                        padding=0,
                        pytorchsim_shape_args=f"{int(m)} {in_features} {out_features}",
                        note="Linear is mapped to GEMM M K N.",
                    )
                )

        return hook

    for name, module in model.named_modules():
        if isinstance(module, (torch.nn.Conv2d, torch.nn.Linear)):
            hooks.append(module.register_forward_hook(add_hook(name, module)))
    return hooks


def load_unet(model_id: str, local_files_only: bool):
    if torch is None:
        raise RuntimeError("PyTorch is required to trace model shapes.")
    from diffusers import UNet2DConditionModel

    return UNet2DConditionModel.from_pretrained(
        model_id,
        subfolder="unet",
        torch_dtype=torch.float32,
        local_files_only=local_files_only,
    )


def run_unet_trace(model_id: str, out_csv: Path, local_files_only: bool):
    model = load_unet(model_id, local_files_only=local_files_only)
    model.eval()
    rows: list[OpShape] = []
    hooks = register_hooks(model, rows)

    sample = torch.randn(1, 4, 64, 64)
    timestep = torch.tensor([500], dtype=torch.long)
    encoder_hidden_states = torch.randn(1, 77, model.config.cross_attention_dim)

    with torch.no_grad():
        model(sample, timestep, encoder_hidden_states=encoder_hidden_states)

    for hook in hooks:
        hook.remove()

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()) if rows else ["op_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    print(f"wrote {out_csv} with {len(rows)} operator rows")


def run_synthetic_unet_trace(out_csv: Path):
    if torch is None:
        raise RuntimeError("PyTorch is required to trace model shapes.")
    from diffusers.models.unets.unet_2d_condition import UNet2DConditionModel

    model = UNet2DConditionModel(
        sample_size=32,
        in_channels=4,
        out_channels=4,
        down_block_types=("CrossAttnDownBlock2D", "DownBlock2D"),
        up_block_types=("UpBlock2D", "CrossAttnUpBlock2D"),
        block_out_channels=(64, 64),
        layers_per_block=[1, 1],
        cross_attention_dim=[768, 768],
        attention_head_dim=(8, 8),
    ).to("cpu").eval()

    rows: list[OpShape] = []
    hooks = register_hooks(model, rows)

    g = torch.Generator().manual_seed(0)
    sample = torch.randn(1, 4, 32, 32, generator=g)
    timestep = torch.randint(low=0, high=1000, size=(1,), generator=g, dtype=torch.long)
    encoder_hidden_states = torch.randn(1, 77, 768, generator=g)

    with torch.no_grad():
        model(sample=sample, timestep=timestep, encoder_hidden_states=encoder_hidden_states)

    for hook in hooks:
        hook.remove()

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()) if rows else ["op_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    print(f"wrote {out_csv} with {len(rows)} operator rows")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="runwayml/stable-diffusion-v1-5")
    parser.add_argument("--out", default="results/flood_traces/sd15_unet_shapes.csv")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--synthetic-unet", action="store_true")
    args = parser.parse_args()

    if args.synthetic_unet:
        run_synthetic_unet_trace(out_csv=Path(args.out))
    else:
        run_unet_trace(
            model_id=args.model_id,
            out_csv=Path(args.out),
            local_files_only=not args.allow_download,
        )


if __name__ == "__main__":
    main()
