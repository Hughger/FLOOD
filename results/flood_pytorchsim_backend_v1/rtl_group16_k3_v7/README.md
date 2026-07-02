# FLOOD RTL Group16 k3 Calibration v7

## 目的

本报告补上真实卷积 workload 最关键的 `k=3/group_size=16/res=1` RTL-clean 证据。所有样本均使用 SRAM memory 初始清零 testbench，并由探针确认无 X。

## v7 规则

对 `k=3/group_size=16/res_cols=res_rows=1`：

```text
final_run = 147*cout + 38
nonfinal_run = final_run - 3
total = (cin_idx_total-1)*nonfinal_run + final_run
```

## 验证结果

| split | total | rtl clean | blocked | mean abs err % | max abs err % |
|---|---:|---:|---:|---:|---:|
| fit | 5 | 5 | 0 | 0.0 | 0.0 |
| holdout | 4 | 4 | 0 | 0.0 | 0.0 |

## 明细

| case | split | cout | cin | cycles | measured | v7 pred | err % |
|---|---|---:|---:|---|---:|---:|---:|
| `k3_c2_g16_ci1` | fit | 2 | 1 | `332` | 332 | 332.0 | 0.0 |
| `k3_c4_g16_ci1` | fit | 4 | 1 | `626` | 626 | 626.0 | 0.0 |
| `k3_c6_g16_ci1` | fit | 6 | 1 | `920` | 920 | 920.0 | 0.0 |
| `k3_c2_g16_ci2` | fit | 2 | 2 | `329;332` | 661 | 661.0 | 0.0 |
| `k3_c4_g16_ci2` | fit | 4 | 2 | `623;626` | 1249 | 1249.0 | 0.0 |
| `k3_h_c3_g16_ci1` | holdout | 3 | 1 | `479` | 479 | 479.0 | 0.0 |
| `k3_h_c5_g16_ci1` | holdout | 5 | 1 | `773` | 773 | 773.0 | 0.0 |
| `k3_h_c3_g16_ci3` | holdout | 3 | 3 | `476;476;479` | 1431 | 1431.0 | 0.0 |
| `k3_h_c5_g16_ci3` | holdout | 5 | 3 | `770;770;773` | 2313 | 2313.0 | 0.0 |

## 论文使用建议

`k=3/group16/res=1` 现在已有 fitting 与 holdout 的 A 级 RTL-clean 证据。这可以支撑真实 conv workload 的 kernel-size 校准项；但大 workload 的大量 spatial points 仍应标注为 calibrated projection。
