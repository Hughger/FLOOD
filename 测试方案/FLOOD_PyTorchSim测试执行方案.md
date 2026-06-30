# FLOOD HPCA 重投：PyTorchSim 测试执行方案

## 1. 测试目标

本轮测试不是简单补充更多性能数字，而是用一条统一、可复现的数据链证明三件事：

1. FLOOD 在真实 Diffusion 工作负载上获得端到端收益；
2. 稀疏、混合精度、outlier、Softmax 与双 dataflow 之间存在协同关系，而非独立模块拼装；
3. 所有主结果都能追溯到明确的模型、层、硬件配置和仿真版本。

统一数据链：

```text
PyTorch 模型与输入
  -> 算子与张量 trace
  -> 精度/稀疏/映射标注
  -> PyTorchSim 映射与周期仿真
  -> SRAM/DRAM/NoC 活动统计
  -> 能耗模型
  -> 分层 CSV
  -> 端到端汇总与论文图表
```

## 2. 核心研究问题

| ID | 研究问题 | 需要给出的证据 |
|---|---|---|
| RQ1 | FLOOD 是否真正改善端到端 Diffusion 推理？ | latency、energy、utilization、traffic 的端到端比较 |
| RQ2 | 收益来自哪些模块？ | 逐项消融和增量收益 |
| RQ3 | 各模块为什么必须联合设计？ | 错误组合、固定策略和 oracle 上界对比 |
| RQ4 | 细粒度稀疏是否转化为实际周期和访存收益？ | 真实层级 sparsity、skip ratio、cycle/traffic reduction |
| RQ5 | INT4/INT8 是否在可接受质量损失下带来系统收益？ | quality–latency–energy Pareto 曲线 |
| RQ6 | FLOOD/PLANE 自适应映射是否优于固定 dataflow？ | per-op 最优选择、切换开销、端到端收益 |
| RQ7 | 结论是否只对单一模型成立？ | LDM 与 DiT 两类模型、多分辨率/序列长度结果 |

## 3. 测试对象与固定输入

### 3.1 主模型

| 模型 | 建议配置 | 用途 |
|---|---|---|
| Stable Diffusion v1.5 UNet | batch=1，512×512，固定 20/50 steps | Conv、attention、timestep 变化、端到端主结果 |
| Stable Diffusion v1.5 VAE Decoder | batch=1，512×512 | Conv/upsample 与完整 LDM pipeline |
| DiT-B/4 | batch=1，256×256 | Matrix、attention、Softmax 主结果 |
| DiT-S/4 | batch=1，256×256 | 小模型/规模变化验证 |
| DiT-XL/2 | batch=1，256×256，可选 | 大模型 scaling |

第一轮只跑代表性单步和完整单次网络前向，用于调通；正式结果再按固定 diffusion steps 汇总。所有软件质量实验必须固定 seed、prompt、scheduler、step 数和数据集子集。

### 3.2 建议的正式输入集

- 性能仿真：每个模型至少 3 个固定 seed；由于硬件周期主要由 shape 和稀疏模式决定，报告均值并给出稀疏导致的波动。
- 生成质量：至少 1,000 张用于初步筛选，最终关键配置建议 5,000–10,000 张。
- 重建质量：CelebA-HQ/FFHQ 固定子集，报告 PSNR、SSIM、LPIPS。
- 文生图质量：优先 FID、CLIP Score；PSNR/SSIM 不适合作为无配对文生图的唯一指标。

## 4. 统一硬件配置

正式跑数前冻结 `hardware_config.yaml`，至少包含：

```yaml
technology_nm:
frequency_mhz:
num_cores:
tiles_per_core:
macs_per_tile:
int8_peak_ops:
int4_peak_ops:
weight_sram_kb:
activation_sram_kb:
output_sram_kb:
noc_width_bit:
dram_bandwidth_gbps:
softmax_lanes: 32
precision_switch_cycles: 2
dataflow_switch_cycles:
bitmap_fetch_cycles:
outlier_queue_depth:
```

测试必须区分两类比较：

- **等资源比较**：相同 PE/MAC 数、SRAM、带宽、频率，比较架构和调度效率；
- **实现结果比较**：使用各设计真实综合/P&R 参数，比较面积、功耗和 TOPS/W。

两类结果不能混在同一柱状图中。

## 5. Trace 获取方案

### 5.1 算子级静态字段

每个算子记录：

```text
model, sample_id, diffusion_step, layer_id, op_type,
input_shape, weight_shape, output_shape,
kernel, stride, padding, groups,
M, N, K, heads, sequence_length,
weight_bits, activation_bits, accumulator_bits,
candidate_dataflows
```

覆盖 `Conv2d`、`Linear/GEMM`、`BMM`、Softmax、LayerNorm/GroupNorm、激活、残差加法、上/下采样和数据搬移。非 MAC 算子不能直接忽略，否则端到端 latency 会被高估加速比。

### 5.2 动态统计字段

```text
activation_zero_ratio,
weight_zero_ratio,
zero_channel_group_ratio,
effective_skipped_mac_ratio,
outlier_ratio,
outlier_collision_ratio,
activation_min/max,
percentile_99/99.9/99.99,
selected_precision,
selected_dataflow
```

动态激活建议至少在早、中、晚三个 diffusion step 取样，验证稀疏度和 outlier 是否随 timestep 变化。若变化明显，端到端仿真必须按 step 加权，不能只用单一步骤代表整条采样链。

### 5.3 Trace 正确性检查

每个模型先完成以下校验：

1. PyTorch 统计的总 MAC 数与独立 profiler 误差小于 1%；
2. 各算子输入输出 shape 连续一致；
3. 总参数量与官方模型一致；
4. trace 重放后的算子顺序与原始 forward 一致；
5. dense 配置下 PyTorchSim 周期趋势与理论 roofline 一致。

## 6. PyTorchSim 建模

### 6.1 每层周期分解

每层至少输出：

```text
compute_cycles
weight_load_cycles
activation_load_cycles
output_store_cycles
metadata_cycles
softmax_cycles
outlier_cycles
precision_switch_cycles
dataflow_switch_cycles
stall_cycles
total_cycles
```

若计算与搬移可重叠，使用事件时间线计算总周期，不能简单相加。

### 6.2 稀疏机制开关

| 配置 | 行为 |
|---|---|
| Dense | 不跳零、不门控 |
| ValueSkip | 动态零值不触发 MAC，但仍产生必要取数/控制开销 |
| ValueSkip+Prune | 同时缩短无效加法树活动 |
| GCSE | 全零 32-channel group 跳过 weight SRAM、NoC 和计算 |
| FullSparse | ValueSkip + Prune + GCSE |

关键是把“省 MAC”和“省周期/访存”分开记录。Value-level gating 可能主要省动态能耗，而 GCSE 才可能减少执行周期和数据搬移。

### 6.3 精度和 outlier 开关

| 配置 | 主数据通路 | Outlier |
|---|---|---|
| FP16 reference | FP16 | 无 |
| INT8 | INT8 | 截断/饱和 |
| INT4 | INT4 | 截断/饱和 |
| Mixed | layer-wise INT4/INT8 | 无 |
| Mixed+Outlier | layer-wise INT4/INT8 | bypass 补偿 |

outlier 仿真需要建模共享资源排队。如果同周期多个 lane 出现 outlier，应统计 arbitration collision、队列占用和额外周期，不能只按 outlier 数量线性加一个常数。

### 6.4 Dataflow 开关

| 配置 | 说明 |
|---|---|
| FLOOD-only | 全部算子固定 FLOOD dataflow |
| PLANE-only | 全部算子固定 PLANE dataflow |
| Rule-based adaptive | 按算子 shape、复用和带宽压力选择 |
| Oracle adaptive | 每层分别仿真两种 dataflow，选择总周期较小者 |
| Wrong mapping | 故意选择较差 dataflow，量化错误选择代价 |

建议先用 Oracle 得到性能上界，再设计可解释的 rule-based 策略。论文必须报告 rule-based 与 oracle 的差距，证明选择准则足够有效。

## 7. 实验矩阵

### P0-1：端到端主结果

模型：SD UNet、SD VAE、DiT-B/4、DiT-S/4。

对比：

1. Dense Base FLOOD；
2. Base + 统一 INT8；
3. Full FLOOD；
4. 等资源固定 systolic/GEMM baseline；
5. 可可靠复现时，再加入 diffusion accelerator modeled baseline。

指标：latency、speedup、energy、EDP、utilization、DRAM traffic、SRAM traffic、stall ratio。

### P0-2：稀疏收益

- 真实 workload：逐层 weight/activation/group sparsity 与 cycle/energy reduction；
- synthetic sweep：activation sparsity × weight sparsity 的 11×11 网格；
- group size sweep：8/16/32/64，验证 32-channel 选择；
- metadata 开销：bitmap 容量、fetch 周期和带宽占比。

需要同时给出：

- 稀疏度；
- 理论可跳 MAC；
- 实际跳过 MAC；
- 实际周期减少；
- 实际能耗减少。

### P0-3：混合精度 Pareto

配置：FP16、INT8、INT4、固定比例 Mixed、sensitivity-based Mixed、Mixed+Outlier。

输出：

- x 轴：quality drop；
- y 轴：latency 或 energy；
- 气泡大小：peak memory 或 DRAM traffic。

不要只测“30% INT4”一个点。至少给出 0%、10%、30%、50%、70%、100% INT4，并标出最终选择。

### P0-4：双 dataflow 与存储系统

- FLOOD-only、PLANE-only、adaptive、oracle；
- DRAM bandwidth sweep：8/16/32/64 B/cycle 或对应 GB/s；
- SRAM capacity sweep：0.5×/1×/2×；
- 报告每类算子的 dataflow 选择比例和切换次数；
- 报告切换开销占总周期比例。

### P0-5：系统级消融与协同

建议采用增量和 leave-one-out 两种消融：

```text
Base
+ ValueSkip
+ GCSE
+ Mixed Precision
+ Outlier
+ Softmax
+ Adaptive Dataflow
= Full FLOOD
```

以及：

```text
Full FLOOD
- GCSE
- Mixed Precision
- Outlier
- Adaptive Dataflow
```

增量消融显示收益来源，leave-one-out 显示每个模块在完整系统中的必要性。

重点增加三个“反例”：

1. 高稀疏但固定错误 dataflow；
2. 高 INT4 比例但无 outlier；
3. 只跳 MAC、仍搬运零 weight。

这些反例直接用于回应“只是把已有模块拼起来”的审稿意见。

### P0-6：Softmax

- vector length：32、64、128、256、512、1024、2048；
- 比较标准 FP32/FP16 Softmax、I-BERT-like、FLOOD INT8；
- 指标：最大/平均相对误差、KL divergence、延迟、能耗；
- 在 DiT-B/4 上报告端到端质量影响，而不仅是算子误差。

### P1：Timestep、分辨率与规模敏感性

- SD：256/512/768 分辨率；
- DiT：S/4、B/4、XL/2；
- diffusion early/middle/late timestep；
- batch size 1 为主，可附 batch 2/4；
- 带宽和 SRAM 容量敏感性。

## 8. 能耗与面积数据来源

PyTorchSim 负责活动计数和周期，硬件工具负责单位事件能耗/功耗。建议：

```text
E_total =
  N_MAC_int4 * E_MAC_int4
+ N_MAC_int8 * E_MAC_int8
+ N_SRAM_read/write * E_SRAM
+ N_DRAM_byte * E_DRAM_per_byte
+ N_NoC_flit * E_NoC
+ N_softmax * E_softmax
+ N_outlier_event * E_outlier
+ leakage_power * latency
```

单位事件系数必须注明来源：RTL 仿真、综合、P&R、存储建模工具或公开文献。PyTorchSim 本身不能替代 ASIC PPA 证据。

## 9. 数据文件规范

建议目录：

```text
results/
  manifest.json
  hardware_config.yaml
  traces/
    op_trace.csv
    sparsity_trace.csv
    outlier_trace.csv
  layer_results/
    cycles.csv
    traffic.csv
    energy.csv
  model_results/
    end_to_end.csv
    quality.csv
  figures/
```

每行结果必须包含：

```text
git_commit, simulator_version, config_hash,
model, seed, input, diffusion_steps,
experiment_id, mechanism_flags,
latency, energy, traffic, utilization,
data_source, timestamp
```

其中 `data_source` 只能使用明确枚举：

```text
PyTorch measurement
PyTorchSim cycle simulation
RTL simulation
FPGA measurement
ASIC synthesis
post-layout estimate
analytical estimate
literature-reported
```

## 10. 论文图表建议

| 图 | 内容 | 数据来源 |
|---|---|---|
| Fig. 10 | 测试平台与从 PyTorch 到 PyTorchSim 的数据链 | 方法图 |
| Fig. 11 | 真实层级稀疏 + synthetic heatmap + GCSE 周期收益 | P0-2 |
| Fig. 12 | mixed precision quality–latency–energy Pareto | P0-3 |
| Fig. 13 | outlier 分布、质量恢复、排队开销和面积开销 | P0-3 |
| Fig. 14 | dataflow 选择、带宽/SRAM sweep、错误映射代价 | P0-4 |
| Fig. 15 | 多模型端到端 latency/energy/utilization 主结果 | P0-1 |
| Fig. 16 | 增量 + leave-one-out 系统消融 | P0-5 |
| Fig. 17 | LDM/DiT、多分辨率/规模的扩展验证 | P1 |

主结果图不要同时混合仿真值、芯片实测值和文献原始值。若必须放在一起，使用不同视觉编码并在图注中明确数据来源。

## 11. 执行顺序

### 阶段 A：最小闭环

1. 冻结硬件参数；
2. 跑通一个 Conv、一个 GEMM、一个 Softmax；
3. 跑通 DiT-S/4 单次 forward；
4. 生成第一版 `op_trace.csv` 和 `cycles.csv`；
5. 校验 dense roofline 和周期分解。

### 阶段 B：核心数据

1. SD UNet 与 DiT-B/4 全 trace；
2. 稀疏、outlier、timestep 分布；
3. Base/Full 端到端结果；
4. 系统消融；
5. dataflow 与带宽 sweep。

### 阶段 C：质量与扩展

1. mixed precision/outlier 质量实验；
2. Softmax 端到端质量；
3. VAE、DiT-S/4、可选 DiT-XL/2；
4. 多分辨率和敏感性分析。

### 阶段 D：审计

1. 检查所有图可由原始 CSV 一键重画；
2. 检查所有百分比可由表格公式复算；
3. 检查 baseline 配置是否等资源；
4. 检查数据来源标签；
5. 检查正文单位和摘要数字一致。

## 12. 首周可交付结果

第一周不要追求把所有模型都跑完，先交付以下最小闭环：

1. FLOOD 固定硬件参数表；
2. DiT-S/4 和 SD UNet 各一个 trace 样例；
3. Conv/GEMM/Softmax 三类算子的周期分解；
4. Dense、ValueSkip、GCSE、FullSparse 四配置的小规模比较；
5. FLOOD-only、PLANE-only、oracle 三配置比较；
6. 一张端到端 latency 初稿图；
7. 一份所有字段齐全的 CSV 样例。

该闭环通过后再批量跑模型，能显著降低后期发现口径错误后全部重跑的风险。

## 13. 启动前必须确认

1. 所指的 PyTorchSim 具体仓库、版本与当前已有接口；
2. FLOOD/PLANE 的精确 dataflow 定义与切换条件；
3. GCSE 的真实 group size、bitmap fetch 和状态跳转开销；
4. INT4/INT8 的实际吞吐关系与两周期切换规则；
5. outlier 阈值、共享资源数量和仲裁规则；
6. Softmax 每周期吞吐与流水线深度；
7. 固定频率、核心数、SRAM、NoC 和 DRAM 带宽；
8. HPCA 主 baseline 的具体论文与可复现程度。

在这八项未冻结前，可以采集模型 trace，但不应生成最终论文性能数字。
