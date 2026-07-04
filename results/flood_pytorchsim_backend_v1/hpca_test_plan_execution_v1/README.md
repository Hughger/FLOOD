# HPCA 测试方案执行状态 v1

## 目的

本表把 `测试方案/FLOOD_HPCA测试结果清单.md` 中的核心实验项，映射到当前已经完成的 PyTorchSim / RTL-aware / RTL direct 证据。它不是论文正文，而是后续补实验的执行看板。

## 当前可支撑的论文数据

| 实验项 | 测试方案目标 | 当前证据 | 可进入论文的位置 | 当前状态 |
|---|---|---|---|---|
| E1 端到端主结果 | 证明 diffusion workload 系统级收益 | 只有 6 行 direct RTL-clean 小 workload；k3 projection 另列 appendix | 主表只能放 direct-clean 子集；不能声称端到端 full workload RTL validated | 部分完成 |
| E2 稀疏/跳零 | 证明稀疏机制收益 | 当前资料主要是 dense/结构映射与周期校准；尚无完整 sparsity sweep | 暂不能作为主结论 | 未完成 |
| E5 Softmax 支持 | 证明 attention softmax 支持可信 | softmax 当前被 gate 为 D_excluded | 不能进入主表 | 阻塞 |
| E6 Dataflow 与存储 | 证明 FLOOD/PLANE mixed Conv/GEMM 映射必要性 | 已有 k1/k3、GEMM/Conv、blocked boundary 与 XPROBE 证据；尚无完整 PLANE/FLOOD 对比 | 可作为方法/限制讨论，不能作为完整消融 | 部分完成 |
| E7 系统级消融 | 证明各机制必要性 | 当前只有 RTL-aware 结构校准与 gate；缺 sparse/quant/outlier/softmax 分解 | 暂不能作为主结论 | 未完成 |
| E8 diffusion 族扩展 | 覆盖 LDM/DiT | workload 表包含 UNet/VAE/DiT 形状，但大多为 projection 或 blocked | 只能放 appendix/projection | 部分完成 |
| E9 baseline 公平性 | 配置透明、公平对比 | 已有 gate、B/C/D 分级、blocked/excluded 清单；缺最终 baseline 能耗/面积归一化 | 方法透明度增强，但性能公平性未闭环 | 部分完成 |

## 当前 gate 结论

- HPCA 主性能表：只允许 `B_direct_rtl_clean_workload_row`，当前 6 行。
- Appendix projection：当前 11 行 k3 projection，已有 res=1 与 spatial=2/4 小探针支撑，但不能当 direct RTL 数据。
- Blocked/excluded：当前 14 行，包括 XPROBE 边界、direct blocked 与 unsupported softmax。

## 下一步最快补强路线

1. **k3 spatial probe 扩展**：`k=3, cout=2, cin=2, spatial=8` 已 clean；下一步若继续补强，可跑 `spatial=16` 或直接选择最小 k3 workload 行做 direct RTL 尝试。
2. **Softmax 处理策略**：若短期不实现 RTL softmax，论文中必须明确 Softmax excluded；若要支撑 DiT 完整性，需要单独 softmax 近似/向量单元测试。
3. **稀疏机制最小闭环**：先做 PyTorchSim 或脚本级 sparsity sweep，生成 skipped MAC ratio / projected cycle reduction，不混入 direct RTL 主表。
4. **能耗/面积闭环**：补 FLOOD 配置、频率、SRAM/DRAM 访问假设和 per-cycle 能耗来源，否则 HPCA 的 energy/power 表不能成立。

## 审稿风险

- 如果把 C 级 projection 写成 full RTL validation，会被直接质疑。
- 如果 softmax 继续 D_excluded，却声称 DiT end-to-end，逻辑不闭合。
- 如果主表只保留 6 行 direct-clean，论文性能贡献偏弱；需要 appendix projection、机制分析或更多 direct-clean k3/spatial 证据来补强叙事。
