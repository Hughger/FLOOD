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
