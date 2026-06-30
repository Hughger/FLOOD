# FLOOD RTL-Aware Model v2

This result applies the same RTL-aware FLOOD model to the traced synthetic UNet Conv/GEMM workload.

## Inputs

- PyTorchSim baseline: `synthetic_unet_unique_baseline_v1.csv`
- FLOOD estimate: `synthetic_unet_unique_flood_rtl_aware_v2.csv`
- Hardware summary: `flood_rtl_hardware_model_v2.yaml`

## RTL Mechanisms Included

- `Config.scala`: 16 tiles, 32 x 32 CIM core, 8-bit data, `tLatency=4`.
- `MacMachine_top.v`: 256-bit weight/feature buses and 512-bit output/joint SRAM buses.
- `Tile.scala`: 1x1 convolution pointwise fast path with no shift-add.
- `Tile.scala`: k>1 convolution shift-add and second output transfer.
- `Cluster.scala`: 16 tile outputs serialized by one round-robin arbiter.

## Interpretation

The trace contains GEMM, spatial convolution, and pointwise convolution rows. v2 reports `rtl_workmode_class` so these can be separated in later tables. The current 16-tile RTL is slower than the PyTorchSim baseline at raw scale; normalized paper-level scenarios are in `results/paper_compare_v2/paper_main_table.md`.
