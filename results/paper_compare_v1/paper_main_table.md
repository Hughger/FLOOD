# Paper-Level Main Result Table

| Dataset | Scenario | Operators | PyTorchSim cycles | FLOOD cycles | FLOOD latency us | Speedup |
|---|---|---|---:|---:|---:|---:|
| synthetic_unet_trace | current_rtl | conv,gemm | 62392.0 | 170199.0 | 181.062766 | 0.366583x |
| synthetic_unet_trace | equal_peak_dense | conv,gemm | 62392.0 | 21148.75 | 22.49867 | 2.950151x |
| synthetic_unet_trace | flood_aggressive | conv,gemm | 62392.0 | 14835.043 | 15.781961 | 4.205718x |
| synthetic_unet_trace | flood_conservative | conv,gemm | 62392.0 | 18967.5325 | 20.178226 | 3.28941x |
| synthetic_unet_trace | flood_main | conv,gemm | 62392.0 | 16844.98 | 17.920191 | 3.703893x |
| workload_v1 | current_rtl | conv,gemm | 760951.0 | 3573042.0 | 3801.108511 | 0.21297x |
| workload_v1 | equal_peak_dense | conv,gemm,softmax | 809140.0 | 494521.75 | 526.086968 | 1.636207x |
| workload_v1 | flood_aggressive | conv,gemm,softmax | 809140.0 | 323122.7795 | 343.747638 | 2.504126x |
| workload_v1 | flood_conservative | conv,gemm,softmax | 809140.0 | 459841.29 | 489.192862 | 1.759607x |
| workload_v1 | flood_main | conv,gemm,softmax | 809140.0 | 389920.1456 | 414.808666 | 2.075143x |
