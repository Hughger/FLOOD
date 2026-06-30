# FLOOD Paper-Level Comparison

This comparison separates current RTL scale from paper-level normalized scenarios.

- PyTorchSim baseline peak assumption: 32768 MAC/cycle
- Current FLOOD RTL peak estimate: 4096 MAC/cycle
- Equal-peak scale factor: 8.00x

| Dataset | Scenario | Operator | Rows | PyTorchSim cycles | FLOOD cycles | Speedup |
|---|---|---|---:|---:|---:|---:|
| synthetic_unet_trace | current_rtl | conv | 11 | 41517.0 | 115781.0 | 0.358582x |
| synthetic_unet_trace | current_rtl | gemm | 10 | 20875.0 | 54418.0 | 0.383605x |
| synthetic_unet_trace | equal_peak_dense | conv | 11 | 41517.0 | 14426.0 | 2.877929x |
| synthetic_unet_trace | equal_peak_dense | gemm | 10 | 20875.0 | 6722.75 | 3.105128x |
| synthetic_unet_trace | flood_aggressive | conv | 11 | 41517.0 | 10230.448 | 4.05818x |
| synthetic_unet_trace | flood_aggressive | gemm | 10 | 20875.0 | 4604.595 | 4.533515x |
| synthetic_unet_trace | flood_conservative | conv | 11 | 41517.0 | 12936.52 | 3.209287x |
| synthetic_unet_trace | flood_conservative | gemm | 10 | 20875.0 | 6031.0125 | 3.461276x |
| synthetic_unet_trace | flood_main | conv | 11 | 41517.0 | 11544.08 | 3.596389x |
| synthetic_unet_trace | flood_main | gemm | 10 | 20875.0 | 5300.9 | 3.938011x |
| workload_v1 | current_rtl | conv | 4 | 665734.0 | 3163850.0 | 0.210419x |
| workload_v1 | current_rtl | gemm | 4 | 95217.0 | 409192.0 | 0.232695x |
| workload_v1 | equal_peak_dense | conv | 4 | 665734.0 | 395382.0 | 1.683774x |
| workload_v1 | equal_peak_dense | gemm | 4 | 95217.0 | 50950.75 | 1.868805x |
| workload_v1 | equal_peak_dense | softmax | 2 | 48189.0 | 48189.0 | 1.0x |
| workload_v1 | flood_aggressive | conv | 4 | 665734.0 | 258940.528 | 2.570992x |
| workload_v1 | flood_aggressive | gemm | 4 | 95217.0 | 33092.574 | 2.877292x |
| workload_v1 | flood_aggressive | softmax | 2 | 48189.0 | 31089.6775 | 1.55x |
| workload_v1 | flood_conservative | conv | 4 | 665734.0 | 372735.28 | 1.786077x |
| workload_v1 | flood_conservative | gemm | 4 | 95217.0 | 46948.51 | 2.028115x |
| workload_v1 | flood_conservative | softmax | 2 | 48189.0 | 40157.5 | 1.2x |
| workload_v1 | flood_main | conv | 4 | 665734.0 | 314264.88 | 2.118385x |
| workload_v1 | flood_main | gemm | 4 | 95217.0 | 39959.71 | 2.382825x |
| workload_v1 | flood_main | softmax | 2 | 48189.0 | 35695.5556 | 1.35x |

## Notes

- `current_rtl` is tied to the visible 16-tile FLOOD implementation.
- `equal_peak_dense` normalizes current FLOOD compute resources to PyTorchSim baseline peak MAC/cycle.
- `flood_conservative`, `flood_main`, and `flood_aggressive` are paper-level sensitivity scenarios.
- Softmax is only included in paper-level scenarios as a planned vector/softmax-unit sensitivity, not current RTL.
