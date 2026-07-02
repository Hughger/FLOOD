# FLOOD PyTorchSim 与 RTL 校准资料库

本仓库整理了 FLOOD 架构与 PyTorchSim baseline 的实验资料、脚本、结果表和 RTL bring-up 校准数据。

当前工作重点不是直接完成完整大模型 RTL 仿真，而是建立一条可复现的评估链路：

```text
PyTorchSim workload / baseline
        ↓
FLOOD 结构映射与 RTL-aware 估算
        ↓
FLOOD Verilog RTL 小/中规模验证
        ↓
RTL 校准公式
        ↓
workload 级 FLOOD calibrated projection
        ↓
选择代表性层继续做 RTL 验证
```

## 快速入口

建议先阅读：

| 文件 | 说明 |
|---|---|
| [FLOOD_PyTorchSim_工作整理.md](./FLOOD_PyTorchSim_%E5%B7%A5%E4%BD%9C%E6%95%B4%E7%90%86.md) | 当前工作流、产出、结论和下一步计划总览 |
| [PyTorchSim_服务器使用说明_任务1_2.md](./PyTorchSim_%E6%9C%8D%E5%8A%A1%E5%99%A8%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E_%E4%BB%BB%E5%8A%A11_2.md) | 给任务 1/2 负责人的服务器运行、CSV 输出和日志记录说明 |
| [team_templates](./team_templates/README.md) | 团队 workload CSV 模板、运行记录模板和自动检查脚本 |
| [中文产出索引.md](./results/flood_pytorchsim_backend_v1/%E4%B8%AD%E6%96%87%E4%BA%A7%E5%87%BA%E7%B4%A2%E5%BC%95.md) | 结果目录索引 |
| [rtl_bringup_calibration_v3](./results/flood_pytorchsim_backend_v1/rtl_bringup_calibration_v3/README.md) | 最新 RTL bring-up 校准报告 |
| [rtl_bringup_workload_v1](./results/flood_pytorchsim_backend_v1/rtl_bringup_workload_v1/README.md) | workload 级 RTL 校准外推结果 |
| [README_mid_validation.md](./results/flood_pytorchsim_backend_v1/rtl_calibration_results/README_mid_validation.md) | 中等规模 RTL 验证说明 |

## 仓库内容

```text
flood_local/
  分析、汇总、RTL 校准和 workload 外推脚本

results/
  PyTorchSim baseline、FLOOD 估算、RTL 校准、论文场景对比等结果

测试方案/
  FLOOD/PyTorchSim 测试方案和执行说明

FLOOD_PyTorchSim_工作整理.md
  中文总文档
```

## 当前 RTL 校准状态

当前已经完成 22 个完整 FLOOD RTL bring-up case，覆盖：

```text
k: 1, 3
cout: 1, 2, 4, 8, 10, 16, 32
group_size: 2, 4, 8, 16
cin_idx_total: 1, 2, 4, 10
res_cols/res_rows: 1 或 2
```

代表性 RTL 周期：

| case | cycles |
|---|---:|
| `k=1, cout=1, group=4, cin=1` | 35 |
| `k=3, cout=2, group=4, cin=1` | 133 |
| `k=1, cout=32, group=4, cin=1` | 438 |
| `k=1, cout=10, group=4, cin=10` | 1493 |
| `k=3, cout=10, group=4, cin=10` | 5623 |

最新校准报告：

```text
results/flood_pytorchsim_backend_v1/rtl_bringup_calibration_v3
```

## 当前结论

1. FLOOD RTL 已经可以通过 testbench 跑通，并产出周期数据。
2. 已修复 testbench 地址错误和 Verilog `x` 未知态污染问题。
3. 目前 22 个 RTL bring-up case 可用于校准 RTL-aware simulator。
4. workload 级结果目前属于 calibrated projection，不是完整 RTL 论文主结果。
5. 若要形成更强论文证据，下一步应迁移到 Verilator 或商业仿真器，并选择代表性 layer 做完整 RTL validation。

## 重要说明

本仓库没有上传本地 SSH 私钥、GitHub 上传 key、大型源码副本和仿真中间产物。

本仓库中的 RTL 校准数据主要用于：

- 证明 FLOOD RTL 流程可运行；
- 校准 RTL-aware simulator；
- 指导下一批代表性 RTL 实验；
- 支撑论文中的 calibrated workload projection。

当前不应直接声称“完整 workload 已经全部通过 RTL 仿真验证”。

## 2026-07-01 可信度提升记录

新增两类资料：

| 文件 | 作用 |
|---|---|
| [rtl_holdout_boundary_validation_v2](./results/flood_pytorchsim_backend_v1/rtl_holdout_boundary_validation_v2/README.md) | 汇总留出样本和边界补测，说明 v3 公式在哪些地方失效 |
| [rtl_boundary_calibration_v4](./results/flood_pytorchsim_backend_v1/rtl_boundary_calibration_v4/README.md) | 候选 v4 校准公式，对当前有效 RTL 样本做一致性拟合 |
| [rtl_v4_independent_validation_v1](./results/flood_pytorchsim_backend_v1/rtl_v4_independent_validation_v1/README.md) | 使用未参与 v4 拟合的新 RTL 点验证 v4 外推能力 |
| [rtl_high_group_repeat_issue_v1](./results/flood_pytorchsim_backend_v1/rtl_high_group_repeat_issue_v1/README.md) | 记录 `group_size=16` 重复执行时后续 run 为 0 的阻塞问题 |
| [rtl_high_group_repeat_fix_v1](./results/flood_pytorchsim_backend_v1/rtl_high_group_repeat_fix_v1/README.md) | 验证清中断/drain 修复后，高 group 多 Cin 不再出现 0 周期 |
| [rtl_group16_multicin_v5](./results/flood_pytorchsim_backend_v1/rtl_group16_multicin_v5/README.md) | 基于修复后 RTL 数据建立 `group_size=16` 多 Cin v5 校准项 |
| [rtl_group16_v5_holdout_v1](./results/flood_pytorchsim_backend_v1/rtl_group16_v5_holdout_v1/README.md) | 使用未参与 v5 拟合的新 RTL 点验证 v5 外推能力 |
| [group16_v5_workload_v1](./results/flood_pytorchsim_backend_v1/group16_v5_workload_v1/README.md) | 将 v5 多 Cin 规则接入 workload 级 FLOOD calibrated projection |
| [rtl_group16_spatial_x_rootcause_v1](./results/flood_pytorchsim_backend_v1/rtl_group16_spatial_x_rootcause_v1/README.md) | 定位 `group_size=16` 空间重复 X 的根因，并验证 SRAM memory 清零后 X 消失 |
| [rtl_group16_spatial_v6](./results/flood_pytorchsim_backend_v1/rtl_group16_spatial_v6/README.md) | 将 `group16/res_cols<=2` 空间重复整理为 v6 RTL-clean 校准/holdout 证据 |
| [paper_data_readiness_v1](./results/flood_pytorchsim_backend_v1/paper_data_readiness_v1/README.md) | 论文数据可用性分级：A 级 RTL-clean、B/C 级 projection、D 级 blocked/excluded |

重要边界结论：

- `k=3/group_size=8` 需要额外交互项，旧公式会低估周期。
- `k=1/group_size=16` 的 `cout` 曲线不能沿用旧的线性项，候选公式为 `56 + 19*max(cout-2,0)`。
- `group_size=16` 且 `cin_idx_total>1` 的 RTL testbench 会出现后续 run 为 0 的异常，暂不能作为论文性能数据。
- v4 是候选校准，不是最终论文证据；下一步必须用新的独立 RTL 样本验证。

2026-07-01 晚间已新增 v4 独立验证：

- 5 个有效独立 RTL 点全部命中 v4。
- 同一批点上 v3 平均绝对误差为 22.4432%。
- `group_size=16` 的空间重复执行也复现后续 run 为 0，说明下一步必须优先修复高 group 重复执行控制路径。

2026-07-02 凌晨新增高 group 重复执行修复验证：

- `group_size=16` 多 Cin 的 0 周期问题已通过 testbench drain-before-clear 策略消除。
- 修复后 `cin=4` 从 `129;0;0;0` 变成 `129;53;53;56`，且没有 X。
- `group_size=16` 空间重复仍有大量 X，暂不能作为论文性能数据。

2026-07-02 上午新增 v5 多 Cin 校准：

- 补跑 `group_size=16, cout=2/4/6/8/12/16, cin=2/4` 共 12 个 RTL 点。
- 所有样本 `x_count=0`，没有 0 周期 run。
- v5 规则：`first_run=19*cout+15`，`middle_run=53`，`final_run=56`。
- 在这 12 个有效样本上，v4 平均绝对误差 `65.5448%`，v5 为 `0%`。

2026-07-02 上午新增 v5 独立验证：

- 新跑 `cout=10/14, cin=3/5` 共 4 个未参与拟合的 RTL 点。
- 所有样本 `x_count=0`，没有 0 周期 run。
- 在这 4 个 holdout 样本上，v4 平均绝对误差 `135.5928%`，v5 为 `0%`。

2026-07-02 上午新增 v5 workload 投影：

- 新增脚本 `flood_local/apply_group16_multicin_v5_workload.py`，把 v5 高 group 多 Cin 规则应用到 workload 表。
- `workload_v1` 的 conv 空间卷积：group16 v5 投影为 `3,197,712` cycles，group4 bring-up 投影为 `42,600,432` cycles，二者比例为 `0.075063`。
- `workload_v1` 的 gemm：group16 v5 投影为 `294,880` cycles，group4 bring-up 投影为 `1,051,808` cycles，二者比例为 `0.280355`。
- 该结果仍应标注为 `RTL-calibrated projection`，不是完整 workload RTL validation；`k=3/group16` 与空间重复路径还需要继续做 RTL 验证。

2026-07-02 上午新增 group16 空间重复 X 根因定位：

- 对 `k=1, cout=12, group_size=16, cin=1, res_cols=2` 重新生成输入并重跑探针。
- 探针确认 `feature_data`、weight 读取、Cluster 输出 NoC 都没有 X。
- X 首次出现在 `OutRouterPlanePost` 读取 output SRAM 高地址 `513..523` 时；这些地址此前未写入，testbench SRAM memory 未初始化导致读出 X。
- 使用 memory 初始清零的 SRAM 模型后，同一 case 周期保持 `246;56`，`x_count` 从 `396/419` 降为 `0`。
- 这说明空间重复路径的下一步应加入明确的 output SRAM 预清零 precondition，并补跑矩阵样本后再纳入论文主数据。

2026-07-02 上午新增 memclear 矩阵补测：

- 补测 `k=1, group_size=16, cin=1, cout=6/12/16, res_cols=2/4`。
- `res_cols=2` 三个样本全部无 X：`132;56`、`246;56`、`322;56`。
- `res_cols=4` 三个样本仍有 X，且探针显示 X 已出现在 Cluster 输出，而不是 Router 读未初始化 SRAM。
- 因此下一版校准应先把 `res_cols=2` 作为可信候选样本，`res_cols>=4` 继续作为 RTL debug 阻塞项。

2026-07-02 上午新增 group16 空间 v6 校准：

- 新增 `rtl_group16_spatial_v6` 报告，将空间重复拆成论文可用区和阻塞区。
- fitting：`cout=6/12/16, res_cols=2`，3 个样本全部无 X，v6 误差 `0%`。
- holdout：`cout=4/8/10/14, res_cols=2`，4 个独立样本全部无 X，v6 误差 `0%`。
- blocked：`res_cols=3/4` 共 7 个样本仍有 X，探针显示 X 在 Cluster 输出侧产生，暂不纳入论文主性能表。

2026-07-02 上午新增论文数据 readiness 分级：

- A 级 RTL-clean 证据：group16 多 Cin v5 fitting `12` 点、holdout `4` 点；group16 空间 v6 fitting `3` 点、holdout `4` 点，误差均为 `0%`。
- B 级 workload projection：18 行落在已验证 k1/group16 规则外推范围内。
- C 级 workload projection：11 行超出当前 group16 clean RTL 边界，主要是 `k=3` 大 Cin conv。
- D 级 excluded/blocked：softmax 不支持，`res_cols>=3` 空间重复仍有 Cluster X。
