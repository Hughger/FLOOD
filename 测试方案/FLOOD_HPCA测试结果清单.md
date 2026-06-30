# FLOOD HPCA 重投 — 测试结果清单

> **用途**：按实验组逐项填写数据，支撑 HPCA 重投实验章节。  
> **论文定位**：FLOOD 作为 **Diffusion 加速器**（面向 LDM/DiT 推理），而非通用 DNN 加速器。  
> **工具链**：开源 PyTorchSim（端到端仿真）+ 固定 FLOOD 硬件参数。  
> **填写说明**：每项结果需注明数据来源（PyTorchSim / FPGA 实测 / RTL 仿真 / ASIC 综合 / P&R 估算）。

---

## 一、统一记录字段（每组实验必填）

| 字段 | 填写内容 |
|---|---|
| 实验组编号 | E1–E9 |
| 模型 | 如 SD v1.5 UNet、DiT-B/4 |
| 输入规模 | batch size、resolution、sequence length |
| 精度配置 | FP16 / INT8 / INT4 / mixed |
| FLOOD 硬件参数 | 频率、Tile/PE 数、buffer、SRAM/DRAM 带宽 |
| Baseline 名称 | 对比对象及配置摘要 |
| 数据来源 | PyTorchSim / FPGA / RTL / ASIC synthesis / P&R estimate |
| 备注 | 异常值、未完成项、待确认项 |

---

## 二、实验结果总表

| 编号 | 实验组 | 论文目的 | 建议模型 | 主要对比 | 需填写指标 | 优先级 | 对应审稿关切 |
|:---:|:---|:---|:---|:---|:---|:---:|:---|
| **E1** | 端到端主结果 | 证明 Full FLOOD 在 diffusion 推理上的系统级收益 | SD v1.5 UNet；VAE；DiT-B/4；DiT-S/4；完整 LDM pipeline | Base FLOOD；DiT-Accel-like；通用 diffusion baseline；Full FLOOD | latency；throughput；energy/power；compute utilization；DRAM/SRAM traffic；speedup | **P0** | 实验可信度、baseline 公平性 |
| **E2** | 细粒度稀疏 | 证明跳零与 GCSE 在 diffusion workload 上有效 | SD UNet；DiT-B/4；VAE | no skipping；zero skipping；+ adder pruning；+ GCSE | activation/weight sparsity；skipped MAC ratio；cycle reduction；energy reduction；utilization | **P0** | 跳零延迟收益、稀疏非已有技术堆砌 |
| **E3** | 混合量化 | 量化性能与生成质量 trade-off | SD UNet；LDM CelebA-HQ/FFHQ；DiT-B/4 | FP16；INT8 all；INT4 all；10%/30%/50% INT4 mixed；sensitivity-based mixed | throughput；peak memory；latency；FID；PSNR；SSIM；LPIPS；CLIP Score；quality drop | **P0** | 精度退化、量化收益 |
| **E4** | Outlier bypass | 证明低成本保精度，而非扩大主 MAC | SD UNet；LDM CelebA-HQ；DiT-B/4 | INT8 truncation；+ outlier bypass；mixed w/o outlier；wide-MAC baseline | outlier ratio；PSNR/SSIM/LPIPS；extra area/power/cycles | **P1** | 量化-精度权衡、硬件开销 |
| **E5** | Softmax 支持 | 证明 DiT attention 关键算子支持可信 | DiT-B/4；DiT-S/4；SD UNet attention 层 | standard Softmax；linear attention；I-BERT-like；FLOOD INT8 Softmax | vector length 32–2048；latency；approximation error；generation quality drop；area/power | **P0** | DiT 推理完整性、非单点优化 |
| **E6** | Dataflow 与存储 | 证明 FLOOD/PLANE 对 mixed Conv/Matrix diffusion 的必要性 | SD UNet；DiT-B/4；完整 LDM pipeline | FLOOD only；PLANE only；adaptive FLOOD+PLANE；固定 GEMM mapping | buffer usage；bandwidth demand；stall cycles；NoC traffic；ping-pong margin；utilization | **P0** | co-design、调度准则 |
| **E7** | 系统级消融 | 回应创新点是否只是拼装 | SD UNet；DiT-B/4；完整 LDM pipeline（可选） | Base；+ sparse；+ quant；+ outlier；+ Softmax；+ dataflow；Full FLOOD | latency；energy；utilization；memory traffic；quality/accuracy drop | **P0** | 组合必要性、收益分解 |
| **E8** | Diffusion 族内扩展 | 证明 FLOOD 覆盖 LDM 与 DiT 两类 diffusion 架构 | SD v1.5（LDM）；DiT-B/4；DiT-S/4；DiT-XL/2（可选） | Base FLOOD；Full FLOOD；DiT-Accel-like | throughput；latency；energy；PSNR/SSIM；generation quality | **P1** | 非单模型特例、diffusion 族适用性 |
| **E9** | Baseline 公平性 | 回应配置不明与比较不公平 | 覆盖 E1–E7 所有 diffusion 主实验 | Base FLOOD；DiT-Accel-like；通用 diffusion baseline；software reference（xDiT/PipeFusion 等，可选） | 工艺；频率；面积；精度；buffer；bandwidth；稀疏/dataflow/Softmax 支持；diffusion mapping 方法 | **P0** | baseline 配置透明 |

**优先级说明**：P0 = HPCA 必补；P1 = 强烈建议补；P2 = 时间允许再补。

---

## 三、分项填写模板

### E1 端到端主结果

| 模型 | 配置 | Latency | Throughput | Energy/Power | Utilization | DRAM Traffic | SRAM Traffic | Speedup vs Base | 数据来源 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| SD UNet | Base FLOOD | | | | | | | 1.00× | |
| SD UNet | Full FLOOD | | | | | | | | |
| SD UNet | DiT-Accel-like | | | | | | | | |
| SD UNet | 通用 diffusion baseline | | | | | | | | |
| VAE | Full FLOOD | | | | | | | | |
| DiT-B/4 | Full FLOOD | | | | | | | | |

**目标结论（待填）**：
- Full FLOOD 相对 Base：latency ↓ ___%，energy ↓ ___%，utilization ↑ ___%
- 相对 DiT-Accel-like / 通用 diffusion baseline 的优势：___

---

### E2 细粒度稀疏

| 模型 | 配置 | Act. Sparsity | Wt. Sparsity | Skipped MAC % | Cycle ↓ | Energy ↓ | Utilization ↑ | 数据来源 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| SD UNet | no skipping | | | | — | — | | |
| SD UNet | zero skipping | | | | | | | |
| SD UNet | + adder pruning | | | | | | | |
| SD UNet | + GCSE | | | | | | | |
| DiT-B/4 | + GCSE | | | | | | | |

**补充**：synthetic sparsity sweep（11×11 网格）热力图数据 — [ ] 已完成

---

### E3 混合量化

| 模型 | 精度配置 | Throughput | Peak Memory | Latency | FID | PSNR | SSIM | LPIPS | CLIP Score | 数据来源 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| SD UNet | FP16 | | | | | | | | | |
| SD UNet | INT8 all | | | | | | | | | |
| SD UNet | INT4 all | | | | | | | | | |
| SD UNet | 30% INT4 mixed | | | | | | | | | |
| SD UNet | sensitivity-based | | | | | | | | | |

**目标结论（待填）**：最优 mixed ratio = ___%，quality drop < ___%

---

### E4 Outlier bypass

| 模型 | 配置 | Outlier Ratio | PSNR | SSIM | LPIPS | Extra Area | Extra Power | Extra Cycles | 数据来源 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| SD UNet | INT8 truncation | | | | | — | — | — | |
| SD UNet | + outlier bypass | | | | | | | | |
| SD UNet | wide-MAC baseline | | | | | | | | |

---

### E5 Softmax 支持

| 模型 | Vector Length | 实现方式 | Latency | Approx. Error | Accuracy Drop | Area | Power | 数据来源 |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|
| DiT-B/4 | 512 | standard Softmax | | | | | | |
| DiT-B/4 | 512 | FLOOD INT8 Softmax | | | | | | |
| DiT-S/4 | 256 | FLOOD INT8 Softmax | | | | | | |
| SD UNet | attention 层 | FLOOD INT8 Softmax | | | | | | |

---

### E6 Dataflow 与存储

| 模型 | Dataflow | Bandwidth | Buffer Size | Latency | Buffer Usage | Stall Cycles | Utilization | 数据来源 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| SD UNet | FLOOD only | 32B | — | | | | | |
| SD UNet | PLANE only | 32B | — | | | | | |
| SD UNet | adaptive | 32B | — | | | | | |
| SD UNet | adaptive | 8B/16B/32B/64B sweep | — | | | | | |

**目标结论（待填）**：adaptive 相对错误 dataflow 的 latency 代价 = ___%

---

### E7 系统级消融

| 配置 | Latency | Energy | Utilization | Memory Traffic | Quality Drop | 数据来源 |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| Base | | | | | — | |
| + zero skipping | | | | | | |
| + adder pruning | | | | | | |
| + GCSE | | | | | | |
| + INT8/INT4 mixed | | | | | | |
| + outlier bypass | | | | | | |
| + Softmax | | | | | | |
| + FLOOD/PLANE dataflow | | | | | | |
| **Full FLOOD** | | | | | | |

---

### E8 Diffusion 族内扩展

| 模型 | 架构类型 | 配置 | Throughput | Latency | Energy | PSNR/SSIM | Generation Quality | 数据来源 |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| SD v1.5 UNet | LDM | Full FLOOD | | | | | | |
| SD VAE | LDM | Full FLOOD | | | | | | |
| DiT-B/4 | DiT | Full FLOOD | | | | | | |
| DiT-S/4 | DiT | Full FLOOD | | | | | | |
| DiT-XL/2 | DiT | Full FLOOD（可选） | | | | | | |

---

### E9 Baseline 公平性配置表

| Baseline | 工艺 | 频率 | 面积 | 精度 | Buffer | Bandwidth | 稀疏支持 | Dataflow | Softmax | Outlier | Mapping | 数据来源 |
|:---|:---:|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---|
| Base FLOOD | | | | | | | | | | | | |
| DiT-Accel-like | | | | | | | | | | | | |
| 通用 diffusion baseline | | | | | | | | | | | | |
| Full FLOOD | | | | | | | | | | | | |

---

## 四、与论文图表的对应关系（建议）

| 论文图号 | 对应实验组 | 主要内容 |
|:---:|:---:|:---|
| Fig. 10 | E9 + 方法说明 | 实验平台、PyTorchSim 流程、数据来源标注 |
| Fig. 11 | E2 | 稀疏机制：热力图 + 真实层级统计 + 消融 |
| Fig. 12 | E3 | 混合量化 trade-off |
| Fig. 13 | E4 | Outlier bypass 质量恢复与硬件开销 |
| Fig. 14 | E5 + E6 | Softmax + dataflow/buffer/bandwidth |
| Fig. 15 | E1 | 端到端主结果（大图） |
| Fig. 16 | E7 | 系统级消融 |
| Fig. 17 | E8 | Diffusion 族内扩展（LDM vs DiT 多模型对比） |

---

## 五、进度跟踪

| 实验组 | 负责人 | 状态 | 预计完成 | 备注 |
|:---:|:---|:---:|:---:|:---|
| E1 | | ⬜ 未开始 | | |
| E2 | | ⬜ 未开始 | | |
| E3 | | ⬜ 未开始 | | |
| E4 | | ⬜ 未开始 | | |
| E5 | | ⬜ 未开始 | | |
| E6 | | ⬜ 未开始 | | |
| E7 | | ⬜ 未开始 | | |
| E8 | | ⬜ 未开始 | | |
| E9 | | ⬜ 未开始 | | |

状态：⬜ 未开始 / 🔄 进行中 / ✅ 已完成

---

*文档版本：v1.1 | 定位：Diffusion Accelerator | 生成日期：2026-06-23*
