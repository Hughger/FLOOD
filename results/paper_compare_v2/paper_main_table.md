# Paper-Level Main Result Table

| Dataset | Scenario | Operators | PyTorchSim cycles | FLOOD cycles | FLOOD latency us | Speedup |
|---|---|---|---:|---:|---:|---:|
| synthetic_unet_trace | current_rtl | conv,gemm | 62392.0 | 203279.0 | 216.254255 | 0.306928x |
| synthetic_unet_trace | equal_peak_dense | conv,gemm | 62392.0 | 25283.75 | 26.897606 | 2.467672x |
| synthetic_unet_trace | flood_aggressive | conv,gemm | 62392.0 | 17522.793 | 18.641269 | 3.56062x |
| synthetic_unet_trace | flood_conservative | conv,gemm | 62392.0 | 22482.2825 | 23.917322 | 2.775163x |
| synthetic_unet_trace | flood_main | conv,gemm | 62392.0 | 19946.2301 | 21.219394 | 3.12801x |
| workload_v1 | current_rtl | conv,gemm | 760951.0 | 3785906.0 | 4027.559574 | 0.200996x |
| workload_v1 | equal_peak_dense | conv,gemm,softmax | 809140.0 | 521129.75 | 554.393351 | 1.552665x |
| workload_v1 | flood_aggressive | conv,gemm,softmax | 809140.0 | 340417.9795 | 362.146787 | 2.376901x |
| workload_v1 | flood_conservative | conv,gemm,softmax | 809140.0 | 482458.09 | 513.253287 | 1.67712x |
| workload_v1 | flood_main | conv,gemm,softmax | 809140.0 | 409876.1456 | 436.038453 | 1.974109x |
