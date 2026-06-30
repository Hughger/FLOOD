# FLOOD RTL-Aware Model v2

This result uses implementation-visible FLOOD mechanisms rather than fixed operator speedups.

## Inputs

- PyTorchSim baseline: `workload_baseline_v1.csv`
- FLOOD estimate: `workload_flood_rtl_aware_v2.csv`
- Hardware summary: `flood_rtl_hardware_model_v2.yaml`

## RTL Mechanisms Included

- `Config.scala`: 16 tiles, 32 x 32 CIM core, 8-bit data, `tLatency=4`.
- `MacMachine_top.v`: 256-bit weight/feature buses and 512-bit output/joint SRAM buses.
- `Tile.scala`: 1x1 convolution pointwise fast path with no shift-add.
- `Tile.scala`: k>1 convolution shift-add and second output transfer.
- `Cluster.scala`: 16 tile outputs serialized by one round-robin arbiter.

## Interpretation

The current visible RTL is smaller than the PyTorchSim TPUv3-like baseline, so direct `current_rtl` comparison is expected to be slower. For paper discussion, use `results/paper_compare_v2/paper_main_table.md`, which separates current RTL scale from equal-peak and FLOOD sensitivity scenarios.

Softmax, outlier bypass, adaptive precision, and sparsity metadata are not treated as current RTL-backed mechanisms in this file.
