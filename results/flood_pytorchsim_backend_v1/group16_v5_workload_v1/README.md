# FLOOD group16 多 Cin v5 workload 投影

## 范围

本目录把已经通过独立 RTL 样本验证的 `group_size=16` 多 Cin v5 规则应用到 workload 行。这一步是 `RTL-calibrated projection`，不是完整 workload RTL validation；原因是当前 `group_size=16` 的空间重复路径仍存在 RTL X 未知态问题。

## 规则

对 `k=1/group_size=16/res=1` 的多 Cin 情况：

```text
first_run = 19*cout + 15
middle_run = 53
final_run = 56
per_spatial = first_run + max(cin_idx_total-2,0)*middle_run + final_run
total = spatial_points * per_spatial
```

## 汇总

`speedup_vs_pytorchsim` 是 PyTorchSim cycles / FLOOD group16 v5 cycles；小于 1 表示当前校准后的 FLOOD 投影周期数高于 PyTorchSim baseline。`vs_group4` 是 group16 v5 / group4 bring-up 投影，用来观察不同 FLOOD 分组策略的相对变化。

| dataset | op | workmode | rows | PyTorchSim cycles | group4 cycles | group16 v5 cycles | speedup_vs_pytorchsim | vs_group4 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| synthetic_unet_trace | conv | pointwise_conv | 4 | 6442.0 | 22080.0 | 25920.0 | 0.248534 | 1.173913 |
| synthetic_unet_trace | conv | spatial_conv | 7 | 35075.0 | 704144.0 | 311760.0 | 0.112506 | 0.44275 |
| synthetic_unet_trace | gemm | gemm | 10 | 20875.0 | 80054.0 | 80446.0 | 0.259491 | 1.004897 |
| workload_v1 | conv | spatial_conv | 4 | 665734.0 | 42600432.0 | 3197712.0 | 0.208191 | 0.075063 |
| workload_v1 | gemm | gemm | 4 | 95217.0 | 1051808.0 | 294880.0 | 0.322901 | 0.280355 |

## 使用边界

这张表可以用于指导论文图表和代表性 layer 选择，但论文中应标注为 `RTL-calibrated projection`。在空间重复路径 X 问题解决前，不应称为完整 workload RTL 验证结果。
