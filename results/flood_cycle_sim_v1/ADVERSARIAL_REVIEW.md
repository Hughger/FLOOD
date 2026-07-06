# FLOOD Cycle Simulator v1 对抗性审查

## 当前结论

`flood_local/flood_cycle_sim.py` 当前是 Base FLOOD MAC datapath 的 cycle-interval simulator。它可以把 GEMM/Conv workload 拆成带起止周期的执行区间，并且已经用现有 direct RTL-clean 样本做回归。

验证结果：

- direct RTL-clean cases: 6
- passed cases: 6
- failed cases: 0
- pass rate: 100%
- max absolute cycle error: 0

权威验证文件：

- `results/flood_cycle_sim_v1/rtl_validation/rtl_validation_summary.csv`
- `results/flood_cycle_sim_v1/rtl_validation/rtl_validation_details.csv`

## 可以主张什么

可以主张：

1. 当前 simulator 对已覆盖的 Base FLOOD MAC run timing 能逐区间复现 RTL-clean 样本。
2. 对支持范围内的 GEMM、k=1 Conv、k=3 Conv，可以输出周期区间、总周期、330MHz 延迟、相对 PyTorchSim baseline 的加速比。
3. 每条 workload 都带 `confidence_grade`，避免把 projection、blocked RTL、direct RTL-clean 混为同等级数据。

## 不能主张什么

不能主张：

1. 这已经是完整芯片级 cycle-accurate simulator。
2. 这已经覆盖 CPU 控制流、DMA、AXI、SRAM 内容正确性、软件调度。
3. 这已经覆盖 softmax、稀疏、跳零、outlier、低成本量化等创新机制。
4. D 级边界样本可以进入论文主性能图。
5. 当前学生 person2 的 30 条 GEMM 能证明 FLOOD 整体优于 PyTorchSim NPU。

## 主要风险

| 风险 | 严重性 | 说明 | 当前处理 |
|---|---:|---|---|
| 误把 calibrated projection 当 direct RTL | 高 | 大部分 workload 不是逐条 RTL-clean | 输出 `confidence_grade` |
| blocked-X 样本被误用 | 高 | 部分大 spatial/multi-Cin 样本出现 X 或 0-cycle | 标为 D 级 |
| 缺少输出值正确性 | 高 | 目前主要验证周期，不验证结果数值 | 暂不进完整正确性结论 |
| 缺少 DMA/CPU/AXI 周期 | 中 | 当前只覆盖 MAC datapath run timing | 后续补 bus/control layer |
| 创新机制未建模 | 高 | softmax/稀疏/跳零/outlier 不在当前 Base RTL clean 证据里 | 不用于创新机制主张 |

## person2 GEMM 复核结论

输入：

- `测试数据/person2/outputs/person2_pytorchsim_transformer.csv`

输出：

- `results/flood_cycle_sim_v1/person2_gemm/workload_summary.csv`

结果：

- rows: 30
- FLOOD faster than PyTorchSim: 9
- FLOOD slower than PyTorchSim: 21
- average speedup: 0.7826x
- max speedup: 2.5291x
- min speedup: 0.1357x

严格结论：person2 这批 GEMM 不适合作为 FLOOD 主优势图；它更适合作为 baseline 交叉检查或反例审查材料。

## 下一步必须补齐

1. 加入 DMA/SRAM/AXI/CPU 控制周期层，至少先做可开关的 fixed/control overhead model。
2. 为 direct RTL blocked 样本保留独立输出，不允许进入 plot-ready 主表。
3. 增加输出值 checker，把周期正确和数值正确分开汇报。
4. 增加 softmax/稀疏/跳零/outlier 的机制开关，但在没有 RTL 证据前默认 `unsupported`。
5. 增加 CI/回归入口：每次修改 simulator 后自动跑 `rtl_validation`，要求 6/6 pass。

