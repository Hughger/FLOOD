# FLOOD Workload Direct RTL Validation v1

## 目的

本报告开始把 workload 行从 `RTL-calibrated projection` 推进到直接 RTL validation。第一批选择 Icarus 可承受的小型 synthetic workload 行，并尝试一个真实 workload GEMM 行。

## 总结

- direct attempted cases: 10
- direct clean cases: 6
- direct blocked cases: 4
- clean row coverage among conv/gemm workload candidates: 20.6897%
- clean direct-vs-projection mean abs error: 0.0%
- clean direct-vs-projection max abs error: 0.0%

## 明细

| case | dataset | workload id | status | direct cycles | projected cycles | err % | x_count | zero cycles |
|---|---|---|---|---:|---:|---:|---:|---:|
| `wd_trace_gemm_001` | synthetic_unet_trace | `trace_gemm_001` | rtl_clean_direct | 223.0 | 223.0 | 0.0 | 0 | 0 |
| `wd_trace_gemm_005` | synthetic_unet_trace | `trace_gemm_005` | rtl_clean_direct | 427.0 | 427.0 | 0.0 | 0 | 0 |
| `wd_trace_gemm_002` | synthetic_unet_trace | `trace_gemm_002` | rtl_clean_direct | 541.0 | 541.0 | 0.0 | 0 | 0 |
| `wd_trace_conv_013` | synthetic_unet_trace | `trace_conv_013` | rtl_clean_direct | 1744.0 | 1744.0 | 0.0 | 0 | 0 |
| `wd_trace_gemm_014` | synthetic_unet_trace | `trace_gemm_014` | rtl_clean_direct | 1744.0 | 1744.0 | 0.0 | 0 | 0 |
| `wd_trace_gemm_015` | synthetic_unet_trace | `trace_gemm_015` | rtl_clean_direct | 2010.0 | 2010.0 | 0.0 | 0 | 0 |
| `wd_attn_score_1024_64_1024` | workload_v1 | `attn_score_1024_64_1024` | observed_blocked_x_and_zero_cycles |  | 43456 |  | 436336 | 25 |
| `wd_trace_conv_018` | synthetic_unet_trace | `trace_conv_018` | observed_blocked_x_with_matching_cycles |  | 3440 |  | 1136 | 0 |
| `wd_trace_gemm_016` | synthetic_unet_trace | `trace_gemm_016` | observed_blocked_x_with_matching_cycles |  | 6832 |  | 1264 | 0 |
| `wd_trace_gemm_008` | synthetic_unet_trace | `trace_gemm_008` | observed_blocked_x_with_matching_cycles |  | 6375 |  | 578 | 0 |

## 阻塞结论

直接 RTL 尝试已经观察到两类阻塞：`attn_score_1024_64_1024` 在大空间循环下出现 `Cluster_OUT` X、Router X 和大量 0-cycle run；`trace_conv_018` 的周期数匹配投影，但 XPROBE2 显示 Cluster/Router/Output 侧存在 X 污染。这些样本不能作为 clean direct RTL 样本；完整 workload RTL validation 的下一步应定位状态清零、输出 SRAM/Router 写读有效性和长空间循环下的 Cluster 状态污染。

## 论文使用建议

这批数据可作为“direct RTL validation 已开始覆盖 workload 子集”的证据。clean synthetic workload 行可进入支撑证据；blocked 行必须单独列为 RTL debug 边界，不进入主性能表。
