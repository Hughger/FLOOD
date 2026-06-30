# Synthetic UNet RTL-Aware FLOOD Model V1

This directory contains the RTL-aware FLOOD estimate for the 21 unique Conv/GEMM shapes traced from the synthetic `UNet2DConditionModel`.

The model uses parameters from the visible FLOOD implementation:

- 16 tiles
- 32 x 32 CIM core per tile
- 8-bit data
- MACTree `tLatency = 4`
- 256-bit feature and weight buses

The output file is:

```text
synthetic_unet_unique_flood_rtl_aware_v1.csv
```

Unlike the earlier fixed-speedup estimate, this version may show FLOOD slower than the PyTorchSim TPUv3-like baseline for some layers. That is expected because this model represents the current RTL-scale implementation, not a normalized paper-scale accelerator.
