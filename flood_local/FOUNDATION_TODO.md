# FLOOD 数据底座建设清单

本清单给负责人使用，不给本科生执行。目标是把本科生提交的 workload CSV 接入 FLOOD simulator/readiness/RTL validation。

## 输入

来自本科生：

```text
week1_submit/*/workload.csv
week1_submit/*/check_report.md
week1_submit/*/run_notes.md
```

必须先通过：

```bash
python team_templates/validate_workload_csv.py <workload.csv> --report <check_report.md>
```

## 底座流程

```text
validated workload CSV
  -> merge_week1_workloads
  -> PyTorchSim baseline cycles check
  -> FLOOD shape mapping
  -> group16 v7 projection
  -> adversarial B/C/D readiness
  -> representative RTL sampling list
```

## 下一批应补的工具

| 工具 | 输入 | 输出 | 状态 |
|---|---|---|---|
| `merge_week1_workloads.py` | 多个 workload.csv | 合并去重 workload | 已有 |
| `check_required_cycles.py` | workload.csv | 缺 cycles 行列表 | 已有 |
| `map_workload_to_flood_shape.py` | workload.csv | FLOOD mapping candidate | 已有部分逻辑，可复用 |
| `apply_group16_v7_workload.py` | FLOOD workload details | projection + scope status | 已有 |
| `build_paper_data_readiness.py` | projection + RTL summary | readiness package | 已有 |
| `select_rtl_validation_subset.py` | readiness details | RTL 抽样清单 | 待写 |

## 已有底座脚本用法

合并多个学生提交的 CSV：

```bash
python flood_local/merge_week1_workloads.py week1_submit/*/workload.csv --out results/flood_pytorchsim_backend_v1/week1_batch_v1/merged_workload.csv --report results/flood_pytorchsim_backend_v1/week1_batch_v1/merge_report.md
```

检查合并表中是否仍有缺失 cycles：

```bash
python flood_local/check_required_cycles.py results/flood_pytorchsim_backend_v1/week1_batch_v1/merged_workload.csv --report results/flood_pytorchsim_backend_v1/week1_batch_v1/cycles_check_report.md
```

## RTL 抽样原则

优先抽：

1. B/C 分界附近；
2. PyTorchSim cycles 占比高的层；
3. 每种 operator 至少 1-2 个代表；
4. 新出现的 shape 边界；
5. 与已知 D 级边界相邻的点。

不要抽：

1. 已知 D_excluded 的 softmax 主表点；
2. 与已有 clean 样本完全重复的 shape；
3. 大到 Icarus 无法完成且没有诊断价值的点。

## 输出目录建议

```text
results/flood_pytorchsim_backend_v1/week1_batch_v1/
  merged_workload.csv
  workload_check_summary.csv
  flood_projection_details.csv
  flood_projection_summary.csv
  readiness_details.csv
  readiness_summary.csv
  rtl_validation_candidates.csv
  README.md
```

## 审查要求

每轮批量数据接入后必须检查：

1. `id` 是否唯一；
2. `operator` 是否只包含允许值；
3. shape 是否可映射；
4. PyTorchSim cycles 是否缺失；
5. FLOOD projection 是否有 status；
6. D 级样本是否被排除出主表；
7. 是否生成 RTL 抽样候选。
