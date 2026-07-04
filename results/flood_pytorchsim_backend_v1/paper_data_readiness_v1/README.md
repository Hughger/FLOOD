# FLOOD Paper Data Readiness v1

## 结论

当前已经具备一批可作为论文材料的 RTL-clean 校准/holdout 证据，但还不具备完整 workload RTL validation。论文主表应把证据等级分开呈现。

## 证据等级定义

- `A_RTL_clean_fit`：直接 RTL 样本，无 X/无 0 周期，用于拟合规则。
- `A_RTL_clean_holdout`：未参与拟合的直接 RTL 样本，无 X/无 0 周期，用于独立验证。
- `B_direct_rtl_clean_workload_row`：该 workload 行已经直接 RTL-clean，并且与 projection 一致。
- `C_projection_*`：有局部 RTL 公式支撑，但该 workload 行没有直接跑通，或空间规模超过已验证边界。
- `D_direct_rtl_blocked`：该 workload 行直接 RTL 尝试已经观察到 X/0-cycle 阻塞。
- `D_excluded/D_blocked_boundary/D_observed_*`：不支持或已知 RTL 阻塞边界，不能进论文主性能表。

## RTL 证据汇总

| evidence | grade | cases | mean abs err % | max abs err % | scope |
|---|---|---:|---:|---:|---|
| group16_multicin_v5_fit | A_RTL_clean_fit | 12 | 0.0 | 0.0 | k=1, group_size=16, res=1, multi-Cin |
| group16_multicin_v5_holdout | A_RTL_clean_holdout | 4 | 0.0 | 0.0 | k=1, group_size=16, res=1, multi-Cin independent cout/cin |
| group16_spatial_v6_fit | A_RTL_clean_fit | 3 | 0.0 | 0.0 | k=1, group_size=16, cin=1, res_cols<=2 |
| group16_spatial_v6_holdout | A_RTL_clean_holdout | 4 | 0.0 | 0.0 | k=1, group_size=16, cin=1, res_cols<=2 |
| group16_spatial_v6_blocked | D_blocked_boundary | 7 | 0.0 | 0.0 | res_cols>=3 blocked by Cluster X |
| group16_k3_v7_fit | A_RTL_clean_fit | 5 | 0.0 | 0.0 | k=3, group_size=16, res=1, cin up to holdout 3 |
| group16_k3_v7_holdout | A_RTL_clean_holdout | 4 | 0.0 | 0.0 | k=3, group_size=16, res=1, cin up to holdout 3 |

## workload readiness 汇总

| grade | rows | PyTorchSim cycles | group16 v7 cycles |
|---|---:|---:|---:|
| B_direct_rtl_clean_workload_row | 6 | 6450.0 | 6689.0 |
| C_projection_large_k3_extent_unvalidated | 11 | 700809.0 | 116271232.0 |
| C_projection_large_spatial_extent_unvalidated | 6 | 51350.0 | 198882.0 |
| C_projection_small_extent_not_directly_run | 2 | 12635.0 | 27193.0 |
| D_direct_rtl_blocked | 3 | 15703.0 | 17818.0 |
| D_excluded | 2 | 48189.0 | 0.0 |
| D_observed_high_cout_multicin_boundary | 1 | 36396.0 | 22186.0 |

## 论文使用建议

论文主数据应优先使用 A 级 RTL-clean fit/holdout 表支撑校准公式；B 级 workload 行可作为 direct RTL-clean workload 子集；C 级只能作为 RTL-calibrated projection；D 级 blocked/excluded 不进入主性能表。
