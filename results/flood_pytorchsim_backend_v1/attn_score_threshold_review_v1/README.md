# Real Workload `attn_score` 阈值审查 v1

## 目的

本报告继续定位真实 workload `attn_score_1024_64_1024` 直接 RTL blocked 的触发条件。

原始 blocked case：

```text
k=1
cout=32
group_size=16
cin_idx_total=2
res_cols=2
res_rows=32
```

之前观察到：`Cluster_OUT` X、Router X、大量 0-cycle run。

## res_rows 扫描

固定 `cout=32, cin=2, res_cols=2`，扫描 `res_rows`：

| case | res_rows | runs | cycles | zero cycles | x_count | cluster_x |
|---|---:|---:|---|---:|---:|---:|
| `thr_attn_score_rr1` | 1 | 4 | `623;56;53;0` | 1 | 0 | 0 |
| `thr_attn_score_rr2` | 2 | 8 | `623;56;53;0;53;0;53;0` | 3 | 0 | 0 |
| `thr_attn_score_rr4` | 4 | 16 | `623;56;53;0;53;0;53;0;53;0;53;0;53;0;53;0` | 7 | 0 | 0 |

结论：0-cycle 在最小 `res_rows=1` 时已经出现，空间循环只是放大这个问题。

## cout 扫描

固定 `cin=2, res_cols=2, res_rows=1`：

| case | cout | cycles | zero cycles | x_count | cluster_x |
|---|---:|---|---:|---:|---:|
| `thr_attn_cout16_rr1` | 16 | `319;56;53;56` | 0 | 0 | 0 |
| `thr_attn_cout24_rr1` | 24 | `471;56;53;56` | 0 | 0 | 0 |
| `thr_attn_score_rr1` | 32 | `623;56;53;0` | 1 | 0 | 0 |

结论：当前更像是高 `cout` 与 `res_cols=2/cin=2` 组合触发的控制边界，而不是单纯大 `res_rows` 问题。

## cout 阈值补测

固定 `cin=2, res_cols=2, res_rows=1`，进一步扫描 `cout=27/28/29/30/32`：

| case | cout | cycles | zero cycles | x_count | cluster_x |
|---|---:|---|---:|---:|---:|
| `thr_attn_cout27_rr1` | 27 | `528;56;53;56` | 0 | 0 | 0 |
| `thr_attn_cout28_rr1` | 28 | `547;56;53;56` | 0 | 0 | 0 |
| `thr_attn_cout29_rr1` | 29 | `566;56;53;0` | 1 | 0 | 0 |
| `thr_attn_cout30_rr1` | 30 | `585;56;53;0` | 1 | 0 | 0 |
| `thr_attn_cout32_rr1_v2` | 32 | `623;56;53;0` | 1 | 0 | 0 |

结论：当前可观测边界稳定在 `cout=28/29` 之间；`cout=27/28` 仍 clean，`cout=29/30/32` 会在最后一个 run 出现 0-cycle。

## 对 simulator 的影响

应新增或保留保守边界：

```text
k=1/group16/cin>=2/res_cols>=2/cout>=29
```

这类行不能被当作普通 C 级 projection；如果 exact workload 已直接观测 blocked，应标为 D 级。

## 下一步

1. 若要继续修 RTL，应重点检查 `cout>=29` 下第二个 spatial column 的 final Cin run 为什么立即 done。
2. 建议改变 `res_cols` 或 `cin_idx_total`，确认该边界是否只绑定 `res_cols=2, cin=2`。
3. 论文主表应继续排除 `attn_score_1024_64_1024` 的直接 RTL 数据，只可作为 blocked case 讨论。
