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

## 修复后的关键分级

来自 `group16_v7_workload_scope_summary.csv`：

```text
B_direct_rtl_clean_workload_row: 5 rows
C_projection_large_k3_extent_unvalidated: 11 rows
C_projection_large_spatial_extent_unvalidated: 6 rows
C_projection_small_extent_not_directly_run: 6 rows
D_direct_rtl_blocked: 1 row
D_excluded: 2 rows
```

来自 `paper_data_readiness_v1`：

```text
B 级 direct-clean workload 行仅 5 个。
C 级 projection 行共 23 个。
D 级 blocked/excluded 行共 3 个。
```

## 当前可用于论文的严谨表述

可以说：

```text
We directly validated a small workload subset on RTL and observed exact agreement with the calibrated simulator.
For larger workload rows, the simulator reports RTL-calibrated projections with explicit scope labels.
One real workload GEMM row was directly attempted and blocked by Cluster-output X and repeated zero-cycle runs.
```

不应说：

```text
The full workload has been RTL validated.
All group16 v7 workload rows have the same confidence level.
The real workload GEMM result is only slow but otherwise valid.
```

## 下一步审查建议

1. 对 `attn_score_1024_64_1024` 做缩小版二分实验：固定 `cout=32, cin=2`，扫描 `res_rows=1/2/4/8/16/32`，定位 Cluster X 的空间循环阈值。
2. 将 simulator 的 C 级 projection 继续细分为“可用作趋势图”和“只能放附录”的两类。
3. 在论文图表生成脚本中强制读取 `adversarial_scope_status`，禁止 D 级样本进入主图。
