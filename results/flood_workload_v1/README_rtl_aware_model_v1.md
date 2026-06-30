# FLOOD RTL-Aware Model V1

This model replaces the earlier fixed speedup assumptions with parameters read from the visible FLOOD implementation.

## Hardware Parameters Used

Source: `FLOOD/src/main/scala/core/Config.scala`

| Parameter | Value |
|---|---:|
| Tile count | 16 |
| CIM core shape per tile | 32 x 32 |
| Data width | 8 bit |
| MACTree pipeline | 2 |
| MACTree tLatency | 4 cycles |
| Weight bus | 256 bit |
| Feature bus | 256 bit |
| Max kernel block Cout | 32 |
| Max kernel block Cin | 1024 |
| Max pixel parallel | 512 |

## Modeling Change

The old `flood_vs_baseline` files used fixed assumptions such as `conv speedup = 1.15x` and `gemm speedup = 1.20x`.

The new RTL-aware model estimates:

- padded MAC work from `shape_args`
- 32-wide reduction tiling
- 32-wide output-channel tiling
- 16-tile parallelism
- MACTree latency
- weight/input/output transfer cycles
- configuration cycles
- convolution shift-add cycles
- simple inter-tile NoC reduction cycles

## Important Interpretation

This is **not** yet the final HPCA FLOOD model.

It is a conservative model of the currently visible RTL/Chisel implementation. Therefore, compared with PyTorchSim's TPUv3-like baseline, some large Conv/GEMM cases may be slower because the baseline uses a much larger 128x128 systolic-style NPU configuration.

That is useful: it prevents us from accidentally claiming paper-level FLOOD speedup from a smaller current RTL implementation.

## Output Files

- `workload_flood_rtl_aware_v1.csv`
- `flood_rtl_hardware_model_v1.yaml`

## Next Modeling Steps

To turn this into a paper-level FLOOD model, the following need to be added explicitly:

- equal-area or equal-peak-compute normalization against PyTorchSim baseline
- softmax/vector unit model if present in the intended architecture
- sparsity/bitmap metadata model
- outlier bypass model
- precision switching model
- real SD v1.5 / VAE / DiT traces
