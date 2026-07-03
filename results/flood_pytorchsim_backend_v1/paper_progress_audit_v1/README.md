# FLOOD HPCA 论文实验进度审查 v1

更新时间：2026-07-03

## 结论

按完整 HPCA 测试方案 E1-E9 严格审查，当前总体完成度估计为：

```text
完整论文实验完成度：18%
我们这边 RTL/simulator 可信度子线：60%
工具链与数据生产底座：45%
可投稿级主结果可信度：30%
```

这个百分比采用保守口径：只有可追溯到 CSV、RTL 日志、readiness 分级或测试方案条目的内容才计入完成；projection 不等同于 full workload RTL validation。

## 当前证据基线

| 项目 | 当前证据 | 审查结论 |
|---|---:|---|
| A 级 RTL-clean fit/holdout | 32 个 clean 样本 | 可用于支撑局部校准公式 |
| workload direct RTL 尝试 | 6 个 case | 覆盖率不足 |
| workload direct-clean | 5/29 candidate rows | 17.2414% |
| workload blocked | 1 个真实 workload + 多个阈值边界点 | 已明确不能进主性能表 |
| workload B 级行 | 5 行 | 可作为 direct-clean workload 子集 |
| workload C 级 projection | 22 行 | 只能作为 RTL-calibrated projection |
| workload D 级 blocked/excluded/boundary | 4 行 | 必须排除出论文主表 |
| attn_score boundary matrix | 16 个阈值 case | 已形成 consolidated blocked/risk 证据 |

## E1-E9 严格进度

| 实验组 | 目标 | 当前完成度 | 主要证据 | 最大缺口 |
|---|---|---:|---|---|
| E1 端到端主结果 | SD/VAE/DiT 端到端 latency/energy/utilization | 10% | 有 workload projection 和少量 direct RTL 子集 | 没有完整 SD/DiT 端到端主表、energy/traffic/utilization |
| E2 细粒度稀疏 | zero skipping/GCSE 真实收益 | 5% | 有早期 workload 和机制设想 | 没有真实 sparsity、skip ratio、cycle/energy reduction |
| E3 混合量化 | INT4/INT8 质量-性能 Pareto | 0% | 暂无可用质量/量化结果 | 缺 FID/CLIP/PSNR/SSIM/LPIPS 与 mixed precision sweep |
| E4 Outlier bypass | outlier 补偿与开销 | 0% | 暂无可用实验 | 缺 outlier ratio、quality recovery、queue/cycle/area/power |
| E5 Softmax | DiT attention softmax 支持 | 5% | 当前 readiness 中 softmax 被 D_excluded | 缺 32-2048 softmax latency/error/quality |
| E6 Dataflow 与存储 | FLOOD/PLANE/adaptive/oracle | 5% | 有 FLOOD RTL projection，暂无 PLANE 对照 | 缺 dataflow sweep、buffer/bandwidth/stall/traffic |
| E7 系统级消融 | Base 到 Full 与 leave-one-out | 0% | 暂无系统消融表 | 缺 sparse/quant/outlier/softmax/dataflow 全组合 |
| E8 Diffusion 扩展 | LDM/DiT 多模型 | 5% | 有 UNet/DiT proxy workload | 缺完整 SD UNet/VAE/DiT-S/B/XL 多模型结果 |
| E9 Baseline 公平性 | 工艺/频率/面积/带宽/配置表 | 10% | 有数据来源分级和审查原则 | 缺冻结硬件参数、baseline 配置表、config hash |

加权估计：

```text
P0 主实验平均完成度约 5%
可信度/RTL 底座完成度约 60%
综合完整论文实验完成度约 18%
```

## 我们这边已完成

1. 打通 FLOOD RTL bring-up、Icarus Verilog 仿真和 testbench 修复。
2. 建立 group16 k1/k3 的 v5/v6/v7 RTL-calibrated simulator。
3. 形成 A 级 RTL-clean fit/holdout 证据。
4. 将 workload projection 拆分为 B/C/D readiness。
5. 对真实 `attn_score_1024_64_1024` blocked 做多维阈值审查。
6. 修复 readiness 过度乐观问题，加入 adversarial scope status。
7. 形成 consolidated boundary matrix，避免单点解释过度。

## 当前不能宣称

1. 不能宣称完整 workload 已 RTL validated。
2. 不能宣称 Full FLOOD 端到端优于 baseline 某个百分比。
3. 不能宣称稀疏、量化、outlier、Softmax 和 dataflow 的协同已经被系统证明。
4. 不能把 C 级 projection 当作 B 级 direct RTL-clean 结果。
5. 不能把 D 级 blocked/excluded 行放入论文主性能表。

## 下一阶段推进门槛

### Gate 1：工具交付给本科生

目标完成度：18% -> 25%

必须交付：

- workload CSV 模板与字段检查脚本；
- trace 到 PyTorchSim 输入的操作说明；
- PyTorchSim baseline cycles 批量运行说明；
- 结果提交目录规范；
- 每个学生的交付样例。

### Gate 2：本科生批量数据回收

目标完成度：25% -> 35%-40%

必须回收：

- SD UNet trace；
- DiT trace；
- PyTorchSim baseline cycles；
- Conv/GEMM/Softmax workload rows；
- 字段齐全、可被 checker 通过的 CSV。

### Gate 3：我们接入 FLOOD projection 与 readiness

目标完成度：35%-40% -> 45%-50%

必须完成：

- 批量 FLOOD projection；
- 自动 B/C/D 分级；
- 代表性层 direct RTL validation 抽样；
- 更新 paper_data_readiness；
- 生成第一版论文主表草稿。

### Gate 4：机制实验最小闭环

目标完成度：45%-50% -> 60%

必须完成：

- Dense/ValueSkip/GCSE/FullSparse 小规模对比；
- FLOOD-only/PLANE/adaptive/oracle 最小对比；
- Softmax 长度 sweep 初版；
- energy/traffic/utilization 字段初版。

## 本周建议百分比目标

如果五位本科生按模板完成 trace/PyTorchSim/baseline 表，我们这边同步完成 projection/readiness 接入，本周合理目标是：

```text
完整论文实验完成度：18% -> 35%-40%
RTL/simulator 可信度子线：60% -> 70%
工具链/数据生产底座：45% -> 75%
```

## 审查原则

每轮推进后必须更新：

1. 当前百分比；
2. 新增证据文件；
3. 哪些数据可进主表；
4. 哪些数据只能进附录；
5. 哪些数据必须排除；
6. 是否已推送 GitHub。
