# FLOOD HPCA 重投 — 测试方案说明（师兄沟通版）

> **文档目的**：与师兄对齐 HPCA 重投实验方向、分工优先级和需要确认的事项。  
> **论文定位**：FLOOD 作为 **Diffusion 加速器**（面向 LDM/DiT 推理），而非通用 DNN 加速器。  
> **配套文档**：[FLOOD_HPCA测试结果清单.md](./FLOOD_HPCA测试结果清单.md)（填表用）

---

## 1. 背景与问题

MICRO 审稿 5 人中 3 人拒稿、4 人质疑 novelty。核心问题不是单一性能数字，而是**论文可信度不足**：

| 审稿关切 | 具体表现 | 对测试的影响 |
|:---|:---|:---|
| 实验来源混杂 | FPGA、ASIC、仿真、估算边界不清 | 必须统一用 PyTorchSim 作为主数据源，并明确标注 |
| Baseline 不公平 | 配置不明，难以判断比较是否合理 | 必须补 baseline 配置表（E9） |
| 创新点像拼装 | 稀疏、量化、dataflow 被视为独立堆叠 | 必须做系统级消融（E7）和错误组合代价 |
| 精度退化未充分报告 | 缺少量化后的质量损失数据 | E3、E4 必须补 FID/PSNR/SSIM 等 |
| 单位口径不一致 | TOPS/GOPS/mm² 混用 | 全文统一单位，测试阶段就按统一口径记录 |

**转投 HPCA 的前提**：按"重投新稿"处理，实验部分需要实质性补强，而非局部改图。

**HPCA 定位调整（相对 MICRO）**：FLOOD 不再主打"通用 DNN 加速器"，而是定位为 **Diffusion 加速器**，专门面向 LDM/DiT 混合 Conv/Matrix 推理。实验、baseline、叙事均围绕 diffusion workload 组织。

---

## 2. 测试策略

### 2.1 核心思路

用**开源 PyTorchSim** 建立统一、可复现的端到端仿真评测，回应审稿人对实验可信度和 baseline 公平性的质疑。

```
PyTorch 模型 → operator trace → FLOOD mapping → PyTorchSim 仿真 → 统一 CSV → 论文图表
```

### 2.2 三条测试主线

| 主线 | 目的 | 对应实验组 |
|:---|:---|:---:|
| **端到端系统级结果** | 支撑摘要核心数字（latency -28%、power -32%、utilization +40%） | E1, E7 |
| **创新点组合有效性** | 证明三项机制联合设计必要，而非简单堆叠 | E2, E3, E4, E5, E6, E7 |
| **审稿驳回点补证据** | 统一数据来源、透明 baseline、规范单位 | E9 + 全文标注 |

### 2.3 与 MICRO 版本的差异

| 维度 | MICRO 版本 | HPCA 重投目标 |
|:---|:---|:---|
| **论文定位** | 通用 DNN 加速器（LDM 为主，扩展到 CNN/ViT/BERT） | **Diffusion 加速器**（LDM + DiT 为核心） |
| 数据来源 | FPGA + ASIC synthesis + 理论估算混写 | PyTorchSim 统一端到端仿真为主 |
| Baseline | NVDLA + DiT-Accelerator，描述不完整 | **Diffusion 专用 baseline 为主**（DiT-Accel、xDiT 等），配置表透明（E9） |
| 消融 | 有但不系统 | 完整 E7 消融 + 错误组合代价 |
| 扩展验证 | ResNet/ViT/BERT 泛化 | **LDM vs DiT 族内多模型对比**（E8） |
| 图表 | 部分实验图缺失 | 按 Fig. 10–17 重新组织 |

---

## 3. 实验组概览（9 组）

| 编号 | 名称 | 优先级 | 核心模型 | 一句话目的 |
|:---:|:---|:---:|:---|:---|
| E1 | 端到端主结果 | **P0** | SD UNet, VAE, DiT-B/4 | 证明 Full FLOOD 系统级收益 |
| E2 | 细粒度稀疏 | **P0** | SD UNet, DiT-B/4 | 证明跳零/GCSE 在真实 workload 有效 |
| E3 | 混合量化 | **P0** | SD UNet, CelebA-HQ | 量化性能与质量 trade-off |
| E4 | Outlier bypass | P1 | SD UNet, CelebA-HQ | 低成本保精度 |
| E5 | Softmax 支持 | **P0** | DiT-B/4, DiT-S/4, SD UNet attention | DiT attention 算子支持可信 |
| E6 | Dataflow 与存储 | **P0** | SD UNet, DiT, LDM pipeline | FLOOD/PLANE 对 mixed Conv/Matrix diffusion 必要性 |
| E7 | 系统级消融 | **P0** | SD UNet, DiT-B/4 | 回应"创新点拼装"质疑 |
| E8 | Diffusion 族内扩展 | P1 | SD v1.5, DiT-B/4, DiT-S/4 | LDM 与 DiT 两类架构均适用 |
| E9 | Baseline 公平性 | **P0** | 全部 diffusion 实验 | 配置透明、比较公平 |

**P0 共 7 组**（E1, E2, E3, E5, E6, E7, E9）— 时间紧时至少完成这些。

---

## 4. 模型选择 rationale

> **原则**：所有主测试模型均为 **diffusion 推理 workload**，不再以 ResNet/ViT/BERT 作为主实验对象。

### 4.1 主测试模型（必做）

| 模型 | 选择理由 | 覆盖算子 | 架构类型 |
|:---|:---|:---|:---:|
| **Stable Diffusion v1.5 UNet** | Diffusion 核心 backbone，Conv+Matrix 混合 | Conv, Attention, Linear, Norm | LDM |
| **Stable Diffusion VAE** | LDM pipeline 编码/解码阶段 | Conv, Deconv | LDM |
| **DiT-B/4** | Diffusion Transformer 代表 | Matrix, Attention, Softmax, MLP | DiT |
| **DiT-S/4** | 较小 DiT 规模，验证 scaling | Matrix, Attention, Softmax | DiT |

### 4.2 扩展模型（建议做，E8）

| 模型 | 选择理由 |
|:---|:---|
| DiT-XL/2 | 更大规模 DiT，验证 scaling |
| 完整 LDM pipeline（UNet+VAE） | 端到端 diffusion 推理 |

### 4.3 不再作为主实验对象

| 模型 | 原因 |
|:---|:---|
| ResNet-50 | 非 diffusion workload，与论文定位不符 |
| ViT-B/16 | 纯分类 Transformer，非 generative |
| BERT-base | NLP 任务，与 diffusion 无关 |

> 若审稿人追问泛化性，可回应：FLOOD 的设计动机来自 diffusion 推理的 mixed Conv/Matrix 特性，实验聚焦 LDM 与 DiT 两类主流 diffusion 架构即可证明适用性。

---

## 5. Baseline 设计

> **原则**：baseline 以 **diffusion 加速器** 为主，不再以 NVDLA 等通用加速器作为主对比对象。

| Baseline | 定位 | 优先级 | 实现方式 |
|:---|:---|:---:|:---|
| **Base FLOOD** | 无三项优化的 FLOOD 原始架构 | 必做 | PyTorchSim 配置 |
| **DiT-Accelerator-like** | 面向 DiT/LDM 的专用 diffusion 加速器 | **必做** | PyTorchSim modeled baseline 或文献数据 |
| **通用 diffusion baseline** | 不针对 mixed Conv/Matrix 优化的 diffusion 加速器 | 建议 | PyTorchSim modeled baseline（同硬件约束） |
| **Software reference** | xDiT、PipeFusion、DistriFusion、TensorRT 等 | 可选 | 单独标注，不与硬件直接公平比较 |
| ~~NVDLA-like~~ | ~~经典通用 DNN 加速器~~ | **不做主 baseline** | 与 diffusion 定位不符，仅可在 related work 中讨论 |

**关键原则**：
- 所有硬件 baseline 在**同一工艺、频率、面积预算、带宽**下比较
- 主对比对象是 **diffusion 领域已有加速器**，而非通用 DNN 加速器
- 若无法完整复现 prior work，写成 "modeled baseline under matched hardware constraints"

---

## 6. 时间线与分工建议

### 6.1 阶段划分

| 阶段 | 时间 | 内容 | 依赖 |
|:---|:---|:---|:---|
| **Phase 0** | 第 1 周 | 确认 FLOOD 硬件参数定稿；选定 PyTorchSim 版本；搭建环境 | 师兄确认硬件参数 |
| **Phase 1** | 第 2–3 周 | PyTorch trace extractor；跑 SD UNet / DiT trace；统计 sparsity/outlier | PyTorchSim 可用 |
| **Phase 2** | 第 4–5 周 | 完成 P0 实验（E1, E2, E3, E6, E7, E9） | Phase 1 完成 |
| **Phase 3** | 第 6 周 | 完成 P1 实验（E4, E5, E8）；汇总填表；出图 | Phase 2 完成 |

### 6.2 分工建议（待与师兄确认）

| 任务 | 建议负责人 | 说明 |
|:---|:---|:---|
| FLOOD 硬件参数定稿 | 师兄 | 频率、Tile 数、buffer、带宽等 |
| PyTorchSim 环境搭建 | 我 | 开源版本选型、配置、验证 |
| Trace extractor | 我 | PyTorch hook 抓 op/shape/sparsity |
| E1–E3 主结果跑数 | 我 | PyTorchSim 端到端仿真 |
| E4–E6 机制实验 | 我 + 师兄 review | 需要确认机制开关配置 |
| E7 消融 | 我 | 按配置逐项开关 |
| E8 泛化 | 我 | 轻量验证 |
| E9 baseline 表 | 师兄主导 | 需要师兄确认 prior work 配置 |
| 论文图表 | 共同 | 我出数据，师兄定图号/布局 |
| 实验段落写作 | 共同 | 我提供数据表，师兄整合 |

---

## 7. 需要与师兄确认的事项

### 7.1 必须确认（阻塞实验启动）

- [ ] **FLOOD 固定硬件参数表**：频率（330 MHz?）、Tile/PE 数、buffer size、SRAM/DRAM 带宽、面积预算（3 mm²?）
- [ ] **开源 PyTorchSim 版本**：GitHub 链接或项目名；输入格式；能否输出 cycle/memory/energy
- [ ] **HPCA 版本三项创新点最终表述**：是否与 MICRO 一致，还是按新手稿重组（稀疏分主动/被动、量化 4/8b、FLOOD 架构提升）
- [ ] **图表安排**：是否沿用 Fig. 10–17 结构，还是按讨论手稿重新编号

### 7.2 建议确认（影响实验设计）

- [ ] **Diffusion baseline 选型**：DiT-Accelerator-like 具体指哪篇 prior work？通用 diffusion baseline 如何建模？
- [ ] **ASIC/FPGA 结果口径**：HPCA 版本中 FPGA 实测、ASIC synthesis 是否保留，还是全部改为 PyTorchSim
- [ ] **精度指标选择**：FID vs PSNR/SSIM 为主（讨论手稿倾向 PSNR/SSIM）
- [ ] **A100 级算力对标**：讨论手稿提到算力与 A100 相当，是否作为 software reference baseline
- [ ] **参考文献 audit**：是否由师兄负责，还是需要我配合核查

### 7.3 讨论手稿中的特殊要求

根据手写讨论记录，以下点需要在实验中体现：

| 讨论要点 | 对应实验 | 状态 |
|:---|:---|:---:|
| 稀疏分主动（GCSE）和被动（slice 跳过） | E2 | 待确认机制开关 |
| 量化 4/8b + outlier 高熵处理 | E3, E4 | 待确认 |
| 延时/功耗/面积三指标 | E1, E9 | 待确认硬件参数 |
| 大图：多模型下 FLOOD vs 他人对比 | E1 + E8 | 待确认对比对象 |
| FID 改 PSNR | E3 | 待确认 |
| Diffusion 模型替换 F16 | E1, E3 | 待确认具体模型 |

---

## 8. 风险与应对

| 风险 | 影响 | 应对 |
|:---|:---|:---|
| PyTorchSim 搭建周期长 | 延迟全部实验 | Phase 1 先用 PyTorch trace 独立推进，不阻塞 |
| PyTorchSim 不支持 energy 输出 | E1/E7 缺 energy 数据 | 自建 energy model（power × latency） |
| NVDLA/DiT-Accel baseline 无法复现 | E1/E9 缺外部对比 | 优先 DiT-Accel-like；通用 diffusion baseline 用 analytical comparison |
| DiT 规模过大跑不动 | E8 scaling 不完整 | 至少覆盖 DiT-B/4 和 DiT-S/4 |
| 时间不够做完全部 9 组 | 实验不完整 | 优先 P0（6 组），P1 酌情砍掉 E5 |

---

## 9. 预期产出

| 产出 | 格式 | 用途 |
|:---|:---|:---|
| 9 组实验 CSV 数据 | `01_trace_layers.csv` 等 | 论文数据来源 |
| 填好的测试结果清单 | `FLOOD_HPCA测试结果清单.md` | 实验章节写作素材 |
| Baseline 配置表 | E9 表格 | 回应审稿人 baseline 质疑 |
| 论文图表数据 | 按 Fig. 10–17 | 直接绑图 |
| 实验方法段落 | LaTeX | 说明数据来源和公平性 |

---

## 10. 一句话总结（给师兄的快速版）

> HPCA 重投将 FLOOD 定位为 **Diffusion 加速器**，用开源 PyTorchSim + 固定硬件参数跑 7 组 P0 实验，主对比对象是 DiT-Accelerator-like 等 diffusion 专用 baseline，主测试模型为 SD UNet/VAE 和 DiT 系列。我负责 PyTorchSim 搭建和跑数，需要师兄确认硬件参数、diffusion baseline 选型和创新点表述。

---

## 附录：与审稿意见的对应关系

| 审稿意见 | 对应实验 | 如何回应 |
|:---|:---:|:---|
| 实验来源混杂 | E9 + 全文标注 | 统一 PyTorchSim，明确标注每类数据来源 |
| Baseline 配置不明 | E9 | 配置表透明 |
| 创新点像拼装 | E7 | 系统级消融 + 错误组合代价 |
| 缺少精度退化数据 | E3, E4 | FID/PSNR/SSIM/LPIPS 全报 |
| 跳零延迟收益不清 | E2 | 真实 workload 层级统计 |
| co-design 论证不足 | E6, E7 | dataflow 选择准则 + 组合必要性 |
| 单位不一致 | 全文 | 测试阶段统一口径 |
| 泛化性不足 | E8 | LDM vs DiT 多模型对比，证明 diffusion 族内适用性 |

---

*文档版本：v1.1 | 定位：Diffusion Accelerator | 生成日期：2026-06-23*
