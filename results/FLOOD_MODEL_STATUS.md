# FLOOD Model Status

## Current Recommended Model

Use the RTL-aware v2 outputs for any discussion tied to the current FLOOD implementation code:

```text
results/flood_workload_v1/workload_flood_rtl_aware_v2.csv
results/synthetic_unet_trace_v1/synthetic_unet_unique_flood_rtl_aware_v2.csv
results/rtl_aware_demo_v2/rtl_aware_readable_summary.md
```

These files are derived from the visible FLOOD implementation parameters:

```text
rowSize = 32
colSize = 32
tileSize = 16
dataWidth = 8
pipeline = 2
tLatency = 4
weightBandWidth = 256 bit
featureMapBandWidth = 256 bit
output_sram_bus_bits = 512 bit
joint_sram_bus_bits = 512 bit
```

v2 also adds RTL-visible control-path costs:

```text
Tile.scala k=1 pointwise fast path
Tile.scala k>1 shift-add path
Tile.scala k>1 second output transfer
Cluster.scala RRArbiter output serialization
MacMachine_top.v 512-bit output/joint SRAM accesses
```

## Paper-Level Normalized Results

Use this table when discussing fair comparison after normalizing FLOOD to the PyTorchSim baseline peak MAC/cycle:

```text
results/paper_compare_v2/paper_main_table.md
```

The `current_rtl` row is tied to the visible 16-tile RTL. The `equal_peak_dense`, `flood_conservative`, `flood_main`, and `flood_aggressive` rows are normalized or sensitivity scenarios, not direct current-RTL measurements.

## Older Placeholder Model

The following files are still useful for pipeline debugging, but should not be treated as paper results:

```text
results/flood_small_loop/flood_vs_baseline.csv
results/flood_workload_v1/workload_flood_vs_baseline_v1.csv
results/synthetic_unet_trace_v1/synthetic_unet_unique_flood_vs_baseline_v1.csv
results/flood_workload_v1/workload_flood_rtl_aware_v1.csv
results/synthetic_unet_trace_v1/synthetic_unet_unique_flood_rtl_aware_v1.csv
results/paper_compare_v1/paper_main_table.md
```

Those files used fixed speedup assumptions such as:

```text
Conv ~= 1.15x
GEMM ~= 1.20x
Softmax ~= 1.30x
```

## Key Interpretation

The RTL-aware model is more honest but more conservative. It represents the current visible implementation, not the full intended FLOOD paper architecture.

If the target paper architecture includes outlier bypass, sparsity metadata, adaptive precision, or a softmax/vector unit, those mechanisms need to be added as explicit modules in the model and backed by either RTL, formulas, or cited assumptions.
