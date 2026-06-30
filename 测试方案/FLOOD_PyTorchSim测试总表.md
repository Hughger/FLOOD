# FLOOD HPCA 重投：PyTorchSim 测试总表

> 本表用于统一确认“从哪些方面测试、测试哪些对象、采集哪些数据”。  
> 具体执行方法见 [FLOOD_PyTorchSim测试执行方案.md](./FLOOD_PyTorchSim测试执行方案.md)，结果填写见 [FLOOD_HPCA测试结果清单.md](./FLOOD_HPCA测试结果清单.md)。

讨论手稿中的实验逻辑可以归纳为三条创新主线：

1. **稀疏优化**：主动稀疏（GCSE）与被动稀疏（运行时 zero/slice skipping）；
2. **低成本量化**：INT4/INT8 可配置计算与高精度 outlier 补偿；
3. **架构扩展**：FLOOD/PLANE 双 dataflow、Softmax、片上存储和多核调度。

实验优先级不按实现难度划分，而按“是否直接支撑论文核心创新和主图”划分。

### P0：必须完成——直接支撑三项创新和论文主结论

| 类别 | 测试内容 | 对应测试 | 必须获得的数据 | 预期支撑 |
|---|---|---|---|---|
| 系统主结果 | 多模型下 FLOOD 与 Base/baseline 的端到端对比 | T1、T2 | latency、energy/power、utilization、speedup、traffic、stall cycles | 手稿中的端到端“大图”，支撑摘要核心数字 |
| 创新一：被动稀疏 | 运行时 zero skipping、adder pruning、无效 slice/group 跳过 | T3、T4 | activation/weight sparsity、skipped MAC、cycle reduction、power reduction | 证明真实稀疏能够转化为计算和功耗收益 |
| 创新一：主动稀疏 | GCSE 训练形成硬件对齐的 channel-group sparsity | T5 | group sparsity、bitmap overhead、SRAM/NoC reduction、latency、energy | 证明 GCSE 不只是普通非结构化剪枝 |
| 创新二：4/8-bit 量化 | INT4/INT8 可配置和 sensitivity-based mixed precision | T6 | INT4 layer ratio、latency、throughput、memory、FID/CLIP/PSNR/SSIM/LPIPS | 找到性能—生成质量 Pareto 最优点 |
| 创新二：高精度 outlier | 少量高精度 outlier 的旁路补偿 | T7 | outlier ratio、quality recovery、extra cycles、area、power | 证明不扩大主计算阵列也能维持质量 |
| 创新三：双 dataflow | FLOOD/PLANE 固定映射、自适应映射和错误映射 | T9 | per-layer dataflow、switch count、latency、utilization、wrong-mapping penalty | 证明 Conv/Matrix 混合负载需要自适应 dataflow |
| 创新三：存储调度 | Buffer、带宽、ping-pong 和多核调度 | T10 | buffer occupancy、bandwidth demand、traffic、stall ratio、ping-pong margin | 支撑手稿中的存储与调度设计 |
| 系统协同 | 三项创新的增量消融和完整系统结果 | T11 | Base 到 Full 的 latency、energy、utilization、traffic、quality 变化 | 回应“创新点只是简单拼装” |
| 实现开销 | 三项创新集成后的面积、功耗和时序 | T17 | area/power breakdown、critical path、frequency、模块开销 | 证明“低成本”和可实现性 |
| 实验可信度 | 固定硬件参数、统一数据源和 baseline 配置 | T16、T18 | 工艺、频率、MAC 数、SRAM、带宽、版本、config hash、数据来源 | 回应 MICRO 审稿中的公平性和可信度质疑 |

### P1：强烈建议——用于证明联合设计必要性

| 类别 | 测试内容 | 对应测试 | 需要获得的数据 | 主要作用 |
|---|---|---|---|---|
| 完整系统反向消融 | 从 Full FLOOD 中逐项移除 GCSE、量化、outlier、dataflow | T12 | latency/energy/utilization/quality 损失 | 证明每个模块在完整系统中不可替代 |
| 错误组合反例 | 高稀疏+错误 dataflow；高 INT4 无 outlier；只跳 MAC 不跳访存 | T13 | latency/energy penalty、quality drop、extra traffic | 最直接回应“已有技术拼装”的质疑 |
| Diffusion 阶段变化 | early/middle/late timestep 的稀疏和 outlier 变化 | T14 | timestep-wise sparsity、outlier、latency、precision/dataflow selection | 证明动态策略比固定策略更合理 |
| Softmax 支持 | 32–2048 长度下 INT8 Softmax 的性能和精度 | T8 | latency、energy、KL divergence、approximation error、质量下降 | 完善 DiT/attention 的端到端算子支持 |
| 模型扩展 | LDM 与不同规模 DiT 的结果 | T15 | speedup、energy、utilization、quality、traffic | 证明结果不是单一 UNet 模型特例 |

### P2：补充实验——用于增强完整性，不阻塞论文主线

| 类别 | 测试内容 | 对应测试或扩展项 | 需要获得的数据 | 使用位置 |
|---|---|---|---|---|
| 更大模型 | DiT-XL/2 或更大分辨率 Stable Diffusion | T15 扩展 | scaling trend、memory、latency、energy | 扩展性图或附录 |
| 大范围参数扫描 | 11×11 稀疏网格、更多 group size、更多 SRAM/带宽点 | T4、T5、T10 扩展 | heatmap 数据、敏感性曲线 | 机制图或附录 |
| 软件参考 | A100、TensorRT、xDiT、PipeFusion 等 | T16 扩展 | software latency、throughput、GPU 配置 | 单独参考，不与等资源硬件结果混比 |
| 通用模型验证 | CNN、ViT、BERT | 可选扩展 | throughput、accuracy、energy | 仅在仍保留“通用性”主张时使用 |
| 更多质量样本 | 扩大生成图像数量和数据集 | T6、T7 扩展 | FID、CLIP、LPIPS 置信区间 | 质量评估附录 |