# FLOOD Paper-Level Comparison

This comparison separates current RTL scale from paper-level normalized scenarios.

- PyTorchSim baseline peak assumption: 32768 MAC/cycle
- Current FLOOD RTL peak estimate: 4096 MAC/cycle
- Equal-peak scale factor: 8.00x

| Dataset | Scenario | Operator | Rows | PyTorchSim cycles | FLOOD cycles | Speedup |
|---|---|---|---:|---:|---:|---:|
| synthetic_unet_trace | current_rtl | conv | 11 | 41517.0 | 134341.0 | 0.309042x |
| synthetic_unet_trace | current_rtl | gemm | 10 | 20875.0 | 68938.0 | 0.302808x |
| synthetic_unet_trace | equal_peak_dense | conv | 11 | 41517.0 | 16746.0 | 2.479219x |
| synthetic_unet_trace | equal_peak_dense | gemm | 10 | 20875.0 | 8537.75 | 2.445024x |
| synthetic_unet_trace | flood_aggressive | conv | 11 | 41517.0 | 11738.448 | 3.536839x |
| synthetic_unet_trace | flood_aggressive | gemm | 10 | 20875.0 | 5784.345 | 3.608879x |
| synthetic_unet_trace | flood_conservative | conv | 11 | 41517.0 | 14908.52 | 2.784783x |
| synthetic_unet_trace | flood_conservative | gemm | 10 | 20875.0 | 7573.7625 | 2.756226x |
| synthetic_unet_trace | flood_main | conv | 11 | 41517.0 | 13284.08 | 3.12532x |
| synthetic_unet_trace | flood_main | gemm | 10 | 20875.0 | 6662.1501 | 3.133373x |
| workload_v1 | current_rtl | conv | 4 | 665734.0 | 3317962.0 | 0.200645x |
| workload_v1 | current_rtl | gemm | 4 | 95217.0 | 467944.0 | 0.203479x |
| workload_v1 | equal_peak_dense | conv | 4 | 665734.0 | 414646.0 | 1.605548x |
| workload_v1 | equal_peak_dense | gemm | 4 | 95217.0 | 58294.75 | 1.633372x |
| workload_v1 | equal_peak_dense | softmax | 2 | 48189.0 | 48189.0 | 1.0x |
| workload_v1 | flood_aggressive | conv | 4 | 665734.0 | 271462.128 | 2.452401x |
| workload_v1 | flood_aggressive | gemm | 4 | 95217.0 | 37866.174 | 2.514566x |
| workload_v1 | flood_aggressive | softmax | 2 | 48189.0 | 31089.6775 | 1.55x |
| workload_v1 | flood_conservative | conv | 4 | 665734.0 | 389109.68 | 1.710916x |
| workload_v1 | flood_conservative | gemm | 4 | 95217.0 | 53190.91 | 1.790099x |
| workload_v1 | flood_conservative | softmax | 2 | 48189.0 | 40157.5 | 1.2x |
| workload_v1 | flood_main | conv | 4 | 665734.0 | 328712.88 | 2.025275x |
| workload_v1 | flood_main | gemm | 4 | 95217.0 | 45467.71 | 2.094167x |
| workload_v1 | flood_main | softmax | 2 | 48189.0 | 35695.5556 | 1.35x |

## Notes

- `current_rtl` is tied to the visible 16-tile FLOOD implementation.
- `equal_peak_dense` normalizes current FLOOD compute resources to PyTorchSim baseline peak MAC/cycle.
- `flood_conservative`, `flood_main`, and `flood_aggressive` are paper-level sensitivity scenarios.
- Softmax is only included in paper-level scenarios as a planned vector/softmax-unit sensitivity, not current RTL.
