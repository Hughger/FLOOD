# FLOOD Simulator 对抗性审查 v1

## 目的

本报告用“假设 simulator 会误导论文结论”的方式审查当前 `group16_v7_workload`、`paper_data_readiness` 和 direct RTL validation 结果。

审查重点：

- 是否把小规模 RTL-clean 公式过度外推到大 workload。
- 是否把 blocked 样本隐藏在 summary 之外。
- 是否存在字段名称让读者误以为是 full workload RTL validation。
- 是否存在已经过期的运行状态描述。

## 发现与修复

| id | 风险 | 严重性 | 发现 | 修复 |
|---|---|---|---|---|
| R1 | workload readiness 过度乐观 | high | 旧版把所有 k1/k3 workload projection 都标成 B 级，但真实 workload `attn_score_1024_64_1024` 已直接 RTL blocked | 将 readiness 改为更严格分级：只有 exact direct-clean 行为 B；真实 blocked 行为 D；其余 projection 降为 C |
| R2 | simulator 输出缺少可信度标签 | high | `group16_v7_workload_details.csv` 只有 projection 结果，单独查看时容易误读为同等级可信 | 新增 `group16_v7_adversarial_scope_status` 和 `group16_v7_adversarial_scope_note`，并生成 `group16_v7_workload_scope_summary.csv` |
| R3 | blocked 状态文档过期 | medium | direct validation 文档曾写“真实 workload 长跑仍在运行”，但后续进程已停止 | 将状态改为 `observed_blocked_x_and_zero_cycles`，说明已在记录阻塞证据后停止 |
| R4 | unsupported operator 不够醒目 | medium | softmax 在 scope summary 中显示为 `unsupported_operator`，不够明确 | 改为 `D_excluded`，防止进入论文主表 |
| R5 | blocked 根因边界不够细 | high | 原先把 `attn_score` blocked 主要描述为大 `res_rows=32`，但扫描发现 `res_rows=1` 已出现 0-cycle；补测进一步显示 `cout=27/28` clean、`cout=29/30/32` blocked，`res_cols=1` clean、`res_cols>=2` blocked，`cin=1` clean、`cin>=2` blocked，group4/8 也未形成 clean 对照 | 新增 `attn_score_threshold_review_v1`，并在 simulator scope 中加入 `cout>=29, cin>=2, res_cols>=2` 高 cout/multi-Cin 边界保护 |
| R6 | k1 空间投影高估宽 Cout 行 | high | `trace_gemm_015` 直接 RTL clean，实测 2010 cycles；旧模型预测 6000 cycles，因为把首个空间块的 Cout 启动开销重复乘到所有空间块 | 将 k1 workload 公式升级为 v8 spatial-reuse：`total=first_spatial+(spatial_points-1)*repeat_spatial`；新增 `trace_gemm_015` clean 证据和 `trace_conv_018` blocked-X 证据 |
| R7 | 周期匹配仍可能掩盖无效输出 | high | `trace_gemm_016` 直接 RTL 与 v8 预测同为 6832 cycles，但 XPROBE2 显示 Cluster/Router/Output 均有 X 污染 | 保留周期模型，将 `trace_gemm_016` 降为 D 级 blocked；后续论文数据必须同时要求 cycle match 和 XPROBE clean |
| R8 | multi-Cin 空间边界过宽 | high | `cout=2, cin=3, res_cols=2, res_rows=8` 边界探针 48 次 run 全部完成且周期匹配 2592，但 XPROBE2 显示 Cluster/Router/Output X | 新增 `spatial_multicin_x_boundary_v1`，并将 `k=1, cin>=3, spatial_points>=16` 降为 D 级边界，除非后续有直接 clean 反证 |
| R9 | 小空间不能保证高 Cin 有效 | high | `trace_gemm_008` 为 `cin=24, spatial=5`，120 次 run 全部完成且周期匹配 6375，但 XPROBE2 仍显示 Cluster/Router/Output X | 将 `trace_gemm_008` 降为 D 级 direct blocked，清除最后一个小规模 C 级 GEMM |

## 修复后的关键分级

来自 `group16_v7_workload_scope_summary.csv`：

```text
B_direct_rtl_clean_workload_row: 6 rows
C_projection_large_k3_extent_unvalidated: 11 rows
C_projection_large_spatial_extent_unvalidated: 3 rows
D_direct_rtl_blocked: 4 rows
D_observed_multicin_spatial_x_boundary: 5 rows
D_excluded: 2 rows
```

来自 `paper_data_readiness_v1`：

```text
B 级 direct-clean workload 行仅 6 个。
C 级 projection 行共 14 个。
D 级 blocked/excluded/boundary 行共 11 个。
```

## 当前可用于论文的严谨表述

可以说：

```text
We directly validated a small workload subset on RTL and observed exact agreement with the calibrated simulator after applying the k1 spatial-reuse correction.
For larger workload rows, the simulator reports RTL-calibrated projections with explicit scope labels.
Blocked direct attempts are reported separately when Cluster/Router/Output X or repeated zero-cycle behavior appears.
```

不应说：

```text
The full workload has been RTL validated.
All group16 v7 workload rows have the same confidence level.
The real workload GEMM result is only slow but otherwise valid.
```

## 下一步审查建议

1. 对 `attn_score_1024_64_1024` 做进一步缩小实验：固定 `cin=2, res_cols=2, res_rows=1`，补 `cout=27` 或改变 `res_cols`，确认 `cout=28/29` 边界是否稳定。
2. 将 simulator 的 C 级 projection 继续细分为“可用作趋势图”和“只能放附录”的两类。
3. 在论文图表生成脚本中强制读取 `adversarial_scope_status`，禁止 D 级样本进入主图。

## v2 阈值更新

已执行第 1 项的前半部分：

- `cout=32, cin=2, res_cols=2` 在 `res_rows=1` 就出现最后一个 run 为 0。
- `cout=16/24/27/28, cin=2, res_cols=2, res_rows=1` 均 clean。
- `cout=29/30/32, cin=2, res_cols=2, res_rows=1` 出现最后一个 run 为 0。
- `cout=29, cin=2, res_rows=1` 下，`res_cols=1` clean，`res_cols=2` 出现 0-cycle，`res_cols=3` 出现 0-cycle 且伴随 Cluster/Router/Output X。
- `cout=29, res_cols=2, res_rows=1` 下，`cin=1` clean，`cin=2/3` 出现 0-cycle。
- `cout=29, cin=2, res_cols=2, res_rows=1` 下，`group_size=4/8` 没有 done interrupt，并出现 Cluster 侧异常摘要；因此不能用小 group 作为 clean 替代证据。
- consolidated boundary matrix 汇总 16 个阈值 case：6 个 clean、7 个 zero-cycle/no-X、1 个 zero-cycle/X、2 个 no-done。
- 因此当前 blocked 边界更接近 `cout>=29, cin>=2, res_cols>=2` 的高 `cout` 多 Cin 多列控制路径，而不是单纯大 `res_rows`；group 维度还需要 RTL 状态机解释。

## v3 k1 空间复用更新

- `trace_gemm_015` 直接 RTL clean：32 个 done interrupt，cycle list 为 `319;56;(53;56)*15`，总计 2010，XPROBE2 全 0。
- 旧模型把 `319;56` 作为每个空间块的固定开销，预测 6000，属于过度保守但会扭曲论文性能趋势的高估。
- 新 v8 规则把第一个空间块和后续空间块分开：首块为 `first_spatial`，后续为空间复用后的 `repeat_spatial`。
- `trace_conv_018` 在周期上匹配 v8/旧公式总计 3440，但 Cluster/Router/Output 出现 X，因此被列为 D 级 blocked，而不是 clean 证据。
- `trace_gemm_016` 进一步证明：即使 cycle count 与 v8 完全一致，也不能自动视为论文可用数据；XPROBE clean 是进入 B 级的硬门槛。
