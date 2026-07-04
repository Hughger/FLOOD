# FLOOD group16 v7 workload 投影

## 范围

本目录把 `k=1` 的 v5/v6 规则和 `k=3` 的 v7 规则应用到 workload。这是 RTL-calibrated projection，不是完整 workload RTL validation。

## 规则

```text
k=1: v8 spatial-reuse rule derived from direct workload RTL rows
k=3: final_run=147*cout+38; nonfinal_run=final_run-3
k=1 total = first_spatial + (spatial_points-1)*repeat_spatial
k=3 total = spatial_points * per_spatial_cycles
```

## 汇总

| dataset | op | workmode | rows | PyTorchSim cycles | group4 cycles | group16 v7 cycles | speedup_vs_pytorchsim | vs_group4 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| synthetic_unet_trace | conv | pointwise_conv | 4 | 6442.0 | 22080.0 | 25920.0 | 0.248534 | 1.173913 |
| synthetic_unet_trace | conv | spatial_conv | 7 | 35075.0 | 704144.0 | 1768720.0 | 0.019831 | 2.511873 |
| synthetic_unet_trace | gemm | gemm | 10 | 20875.0 | 80054.0 | 59698.0 | 0.349677 | 0.745722 |
| workload_v1 | conv | spatial_conv | 4 | 665734.0 | 42600432.0 | 114502512.0 | 0.005814 | 2.687825 |
| workload_v1 | gemm | gemm | 4 | 95217.0 | 1051808.0 | 187150.0 | 0.508774 | 0.177932 |

## 使用边界

k3 v7 已有小规模 fitting/holdout RTL-clean 证据，但 workload 的大空间点数和大 Cin 仍是外推。论文中应标注为 RTL-calibrated projection。

## 对抗性审查分级

| scope status | rows | PyTorchSim cycles | group16 v7 cycles |
|---|---:|---:|---:|
| B_direct_rtl_clean_workload_row | 6 | 6450.0 | 6689.0 |
| C_projection_large_k3_extent_unvalidated | 11 | 700809.0 | 116271232.0 |
| C_projection_large_spatial_extent_unvalidated | 6 | 51350.0 | 198882.0 |
| C_projection_small_extent_not_directly_run | 2 | 12635.0 | 27193.0 |
| D_direct_rtl_blocked | 3 | 15703.0 | 17818.0 |
| D_excluded | 2 | 48189.0 | 0.0 |
| D_observed_high_cout_multicin_boundary | 1 | 36396.0 | 22186.0 |
