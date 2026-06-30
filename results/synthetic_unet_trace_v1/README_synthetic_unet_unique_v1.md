# Synthetic UNet Unique Trace V1 Summary

Unique Conv/GEMM shapes traced from the synthetic UNet2DConditionModel forward pass.

- trace_gemm_001 gemm 1 64 256: baseline 623 cycles, FLOOD estimate 502 cycles, speedup 1.241x.
- trace_gemm_002 gemm 1 256 256: baseline 1101 cycles, FLOOD estimate 880 cycles, speedup 1.251x.
- trace_conv_003 conv 1 32 32 4 64 3 1 1: baseline 6118 cycles, FLOOD estimate 5073 cycles, speedup 1.206x.
- trace_conv_004 conv 1 32 32 64 64 3 1 1: baseline 6796 cycles, FLOOD estimate 5634 cycles, speedup 1.206x.
- trace_gemm_005 gemm 1 256 64: baseline 656 cycles, FLOOD estimate 528 cycles, speedup 1.242x.
- trace_conv_006 conv 1 32 32 64 64 1 1 0: baseline 2117 cycles, FLOOD estimate 1762 cycles, speedup 1.201x.
- trace_gemm_007 gemm 1024 64 64: baseline 1804 cycles, FLOOD estimate 1436 cycles, speedup 1.256x.
- trace_gemm_008 gemm 77 768 64: baseline 1694 cycles, FLOOD estimate 1349 cycles, speedup 1.256x.
- trace_gemm_009 gemm 1024 64 512: baseline 6802 cycles, FLOOD estimate 5386 cycles, speedup 1.263x.
- trace_gemm_010 gemm 1024 256 64: baseline 3611 cycles, FLOOD estimate 2864 cycles, speedup 1.261x.
- trace_conv_011 conv 1 32 32 64 64 3 2 1: baseline 2745 cycles, FLOOD estimate 2281 cycles, speedup 1.203x.
- trace_conv_012 conv 1 16 16 64 64 3 1 1: baseline 2292 cycles, FLOOD estimate 1906 cycles, speedup 1.203x.
- trace_conv_013 conv 1 16 16 64 64 1 1 0: baseline 999 cycles, FLOOD estimate 836 cycles, speedup 1.195x.
- trace_gemm_014 gemm 256 64 64: baseline 940 cycles, FLOOD estimate 753 cycles, speedup 1.248x.
- trace_gemm_015 gemm 256 64 512: baseline 2131 cycles, FLOOD estimate 1694 cycles, speedup 1.258x.
- trace_gemm_016 gemm 256 256 64: baseline 1513 cycles, FLOOD estimate 1206 cycles, speedup 1.255x.
- trace_conv_017 conv 1 16 16 128 64 3 1 1: baseline 2877 cycles, FLOOD estimate 2391 cycles, speedup 1.203x.
- trace_conv_018 conv 1 16 16 128 64 1 1 0: baseline 1120 cycles, FLOOD estimate 936 cycles, speedup 1.197x.
- trace_conv_019 conv 1 32 32 128 64 3 1 1: baseline 8001 cycles, FLOOD estimate 6631 cycles, speedup 1.207x.
- trace_conv_020 conv 1 32 32 128 64 1 1 0: baseline 2206 cycles, FLOOD estimate 1835 cycles, speedup 1.202x.
- trace_conv_021 conv 1 32 32 64 4 3 1 1: baseline 6246 cycles, FLOOD estimate 5179 cycles, speedup 1.206x.
