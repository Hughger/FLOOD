# FLOOD Paper Data Readiness v1

## 结论

当前已经具备一批可作为论文材料的 RTL-clean 校准/holdout 证据，但还不具备完整 workload RTL validation。论文主表应把证据等级分开呈现。

## 证据等级定义

- `A_RTL_clean_fit`：直接 RTL 样本，无 X/无 0 周期，用于拟合规则。
- `A_RTL_clean_holdout`：未参与拟合的直接 RTL 样本，无 X/无 0 周期，用于独立验证。
- `B_projection_from_validated_k1_group16_rules`：workload 行使用已验证 k1/group16 规则外推。
- `C_projection_outside_current_group16_rtl_clean_scope`：workload 行超出当前 clean RTL 边界，只能作为 calibrated projection。
- `D_excluded/D_blocked_boundary`：不支持或已知 RTL 阻塞边界，不能进论文主性能表。

## RTL 证据汇总

| evidence | grade | cases | mean abs err % | max abs err % | scope |
|---|---|---:|---:|---:|---|
| group16_multicin_v5_fit | A_RTL_clean_fit | 12 | 0.0 | 0.0 | k=1, group_size=16, res=1, multi-Cin |
| group16_multicin_v5_holdout | A_RTL_clean_holdout | 4 | 0.0 | 0.0 | k=1, group_size=16, res=1, multi-Cin independent cout/cin |
| group16_spatial_v6_fit | A_RTL_clean_fit | 3 | 0.0 | 0.0 | k=1, group_size=16, cin=1, res_cols<=2 |
| group16_spatial_v6_holdout | A_RTL_clean_holdout | 4 | 0.0 | 0.0 | k=1, group_size=16, cin=1, res_cols<=2 |
| group16_spatial_v6_blocked | D_blocked_boundary | 7 | 0.0 | 0.0 | res_cols>=3 blocked by Cluster X |

## workload readiness 汇总

| grade | rows | PyTorchSim cycles | group16 v5 cycles |
|---|---:|---:|---:|
| B_projection_from_validated_k1_group16_rules | 18 | 122534.0 | 401246.0 |
| C_projection_outside_current_group16_rtl_clean_scope | 11 | 700809.0 | 3509472.0 |
| D_excluded | 2 | 48189.0 | 0.0 |

## 论文使用建议

论文主数据应优先使用 A 级 RTL-clean fit/holdout 表支撑校准公式；B/C 级 workload 结果可以作为 RTL-calibrated projection，并在图注中明确不是 full workload RTL。`res_cols>=3` 和 softmax 暂不进入主性能表。
