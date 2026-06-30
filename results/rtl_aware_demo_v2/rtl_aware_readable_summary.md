# RTL-Aware FLOOD Result Summary

These numbers use the FLOOD implementation-aware model, not fixed speedup assumptions.

## Operator Summary

| Dataset | Operator | Rows | PyTorchSim cycles | FLOOD RTL-aware cycles | FLOOD latency us | Speedup vs PyTorchSim | Utilization |
|---|---|---:|---:|---:|---:|---:|---:|
| synthetic_unet_trace | conv | 11 | 41517 | 134341 | 142.92 | 0.309x | 0.903 |
| synthetic_unet_trace | gemm | 10 | 20875 | 68938 | 73.34 | 0.303x | 0.978 |
| workload_v1 | conv | 4 | 665734 | 3317962 | 3529.75 | 0.201x | 1.000 |
| workload_v1 | gemm | 4 | 95217 | 467944 | 497.81 | 0.203x | 1.000 |

## Top RTL-Aware Cycle Bottlenecks

| Rank | Dataset | ID | Op | Shape | RTL cycles | Latency us | Utilization |
|---:|---|---|---|---|---:|---:|---:|
| 1 | workload_v1 | unet_conv_64_320_320 | conv | 1 64 64 320 320 3 1 1 | 1041786 | 1108.28 | 1.000 |
| 2 | workload_v1 | unet_conv_32_640_640 | conv | 1 32 32 640 640 3 1 1 | 981652 | 1044.31 | 1.000 |
| 3 | workload_v1 | unet_conv_16_1280_1280 | conv | 1 16 16 1280 1280 3 1 1 | 951672 | 1012.42 | 1.000 |
| 4 | workload_v1 | vae_dec_conv_64_256_128 | conv | 1 64 64 256 128 3 1 1 | 342852 | 364.74 | 1.000 |
| 5 | workload_v1 | dit_mlp_256_768_3072 | gemm | 256 768 3072 | 186767 | 198.69 | 1.000 |
| 6 | workload_v1 | attn_qkv_4096_320_320 | gemm | 4096 320 320 | 166531 | 177.16 | 1.000 |
| 7 | workload_v1 | attn_score_1024_64_1024 | gemm | 1024 64 1024 | 67919 | 72.25 | 1.000 |
| 8 | workload_v1 | dit_qkv_256_768_768 | gemm | 256 768 768 | 46727 | 49.71 | 1.000 |
| 9 | synthetic_unet_trace | trace_conv_019 | conv | 1 32 32 128 64 3 1 1 | 42850 | 45.59 | 1.000 |
| 10 | synthetic_unet_trace | trace_gemm_009 | gemm | 1024 64 512 | 33983 | 36.15 | 1.000 |
