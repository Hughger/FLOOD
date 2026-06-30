# FLOOD PyTorchSim Backend Package v1

This package uses PyTorchSim outputs as workload/baseline data and applies a FLOOD RTL-aware backend model.

## Important Interpretation

- PyTorchSim cycles are baseline NPU results.
- `current_rtl` FLOOD cycles are analytical estimates from visible FLOOD RTL/Chisel structure.
- Equal-peak and FLOOD scenarios are normalized/sensitivity results, not RTL simulation.
- Use `calibration_cases.csv` to run small RTL simulations and fill `rtl_sim_cycles`.

## Current RTL Summary

| Dataset | Operator | Workmode | Rows | PyTorchSim cycles | FLOOD cycles | Speedup |
|---|---|---|---:|---:|---:|---:|
| synthetic_unet_trace | conv | pointwise_conv | 4 | 6442.0 | 15976.0 | 0.40323x |
| synthetic_unet_trace | conv | spatial_conv | 7 | 35075.0 | 118365.0 | 0.296329x |
| synthetic_unet_trace | gemm | gemm | 10 | 20875.0 | 68938.0 | 0.302808x |
| workload_v1 | conv | spatial_conv | 4 | 665734.0 | 3317962.0 | 0.200645x |
| workload_v1 | gemm | gemm | 4 | 95217.0 | 467944.0 | 0.203479x |

## Scenario Summary

| Dataset | Scenario | Operators | PyTorchSim cycles | FLOOD cycles | Speedup |
|---|---|---|---:|---:|---:|
| synthetic_unet_trace | current_rtl | conv,gemm | 62392.0 | 203279.0 | 0.306928x |
| synthetic_unet_trace | equal_peak_dense | conv,gemm | 62392.0 | 25283.75 | 2.467672x |
| synthetic_unet_trace | flood_aggressive | conv,gemm | 62392.0 | 17522.793 | 3.56062x |
| synthetic_unet_trace | flood_conservative | conv,gemm | 62392.0 | 22482.2825 | 2.775163x |
| synthetic_unet_trace | flood_main | conv,gemm | 62392.0 | 19946.2301 | 3.12801x |
| workload_v1 | current_rtl | conv,gemm | 760951.0 | 3785906.0 | 0.200996x |
| workload_v1 | equal_peak_dense | conv,gemm,softmax | 809140.0 | 521129.75 | 1.552665x |
| workload_v1 | flood_aggressive | conv,gemm,softmax | 809140.0 | 340417.9795 | 2.376901x |
| workload_v1 | flood_conservative | conv,gemm,softmax | 809140.0 | 482458.09 | 1.67712x |
| workload_v1 | flood_main | conv,gemm,softmax | 809140.0 | 409876.1456 | 1.974109x |
