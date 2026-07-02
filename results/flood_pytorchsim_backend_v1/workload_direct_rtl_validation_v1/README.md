# FLOOD Workload Direct RTL Validation v1

## 目的

本报告开始把 workload 行从 `RTL-calibrated projection` 推进到直接 RTL validation。第一批选择 Icarus 可承受的小型 synthetic workload 行，并尝试一个真实 workload GEMM 行。

## 总结

- direct attempted cases: 6
- direct clean cases: 5
- direct blocked cases: 1
- clean row coverage among conv/gemm workload candidates: 17.2414%
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
| `wd_attn_score_1024_64_1024` | workload_v1 | `attn_score_1024_64_1024` | running_blocked_x_and_zero_cycles |  | 43456 |  | 436336 | 25 |

## 阻塞结论

真实 workload `attn_score_1024_64_1024` 的直接 RTL 长跑仍在服务器上运行，但已观察到 `Cluster_OUT` X、Router X 和大量 0-cycle run，因此不能作为 clean direct RTL 样本。这说明完整 workload RTL validation 的下一步不是继续盲目扩大层规模，而是定位大 `res_rows`/长空间循环下的 Cluster 状态污染。

## 论文使用建议

这批数据可作为“direct RTL validation 已开始覆盖 workload 子集”的证据。5 个 synthetic workload 行已直接 RTL-clean 且与 v7 projection 完全一致；真实 workload 行目前应列为 blocked，不进入主性能表。
