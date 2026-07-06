# FLOOD Cycle Simulator v1 对抗性审查

## 当前结论

`flood_local/flood_cycle_sim.py` 当前是 Base FLOOD MAC datapath 的 cycle-interval simulator。它可以把 GEMM/Conv workload 拆成带起止周期的执行区间，并且已经用现有 direct RTL-clean 样本做回归。

本工具已经包含三层输出：

1. MAC datapath 区间：`cycle_intervals.csv`
2. 系统层区间：`system_intervals.csv`
3. 输出值检查：`value_check_summary.csv` / `value_check_details.csv`

系统层来自当前 RTL 暴露的接口宽度与 DMA 结构：

- `dma_top` 使用 64-bit AXI
- `MacMachine_top` 的 input/weight SRAM 接口为 256-bit
- `MacMachine_top` 的 output/joint SRAM 接口为 512-bit

系统层目前标记为 `unvalidated_system_projection`，不等同于 direct full-chip RTL-clean。

输出值 checker 可以比较 golden 输出和 RTL 输出中的数值 token。若没有同时提供 golden/RTL 输出，正式 workload 的 `value_check_status` 会保持 `missing_evidence`。

## 已验证证据

周期验证：

- direct RTL-clean cases: 6
- passed cases: 6
- failed cases: 0
- pass rate: 100%
- max absolute cycle error: 0

输出值 checker smoke：

- pass case: pass
- fail case: fail
- fail case mismatch count: 1

权威验证文件：

- `results/flood_cycle_sim_v1/rtl_validation/rtl_validation_summary.csv`
- `results/flood_cycle_sim_v1/rtl_validation/rtl_validation_details.csv`
- `results/flood_cycle_sim_v1/value_checker_smoke/pass_case/value_check_summary.csv`
- `results/flood_cycle_sim_v1/value_checker_smoke/fail_case/value_check_summary.csv`

## 可以主张什么

可以主张：

1. 当前 simulator 对已覆盖的 Base FLOOD MAC run timing 能逐区间复现 RTL-clean 样本。
2. 对支持范围内的 GEMM、k=1 Conv、k=3 Conv，可以输出周期区间、总周期、330MHz 延迟、相对 PyTorchSim baseline 的加速比。
3. 每条 workload 都带 `confidence_grade`，避免把 projection、blocked RTL、direct RTL-clean 混为同等级数据。
4. 可以输出未校准系统层区间，用于暴露 DMA/配置开销风险。
5. 可以在提供 golden/RTL 输出文件时执行数值正确性比较。

## 不能主张什么

不能主张：

1. 这已经是完整芯片级 cycle-accurate simulator。
2. 这已经覆盖 CPU 控制流、DMA、AXI、SRAM 内容正确性、软件调度。
3. 当前真实 workload 已经通过输出值正确性验证。
4. 这已经覆盖 softmax、稀疏、跳零、outlier、低成本量化等创新机制。
5. D 级边界样本可以进入论文主性能图。
6. 当前学生 person2 的 30 条 GEMM 能证明 FLOOD 整体优于 PyTorchSim NPU。

## 主要风险

| 风险 | 严重性 | 说明 | 当前处理 |
|---|---:|---|---|
| 误把 calibrated projection 当 direct RTL | 高 | 大部分 workload 不是逐条 RTL-clean | 输出 `confidence_grade` |
| blocked-X 样本被误用 | 高 | 部分大 spatial/multi-Cin 样本出现 X 或 0-cycle | 标为 D 级 |
| 缺少真实 workload 输出值正确性 | 高 | checker 已有，但 person2/synthetic workload 还没有接入 golden/RTL 输出文件 | `value_check_status=missing_evidence` |
| DMA/CPU/AXI 未完成 direct full-chip 校准 | 高 | 当前系统层只基于 RTL 接口宽度和 DMA 结构保守建模 | `system_model_status=unvalidated_system_projection` |
| 创新机制未建模 | 高 | softmax/稀疏/跳零/outlier 不在当前 Base RTL clean 证据里 | 不用于创新机制主张 |

## person2 GEMM 复核结论

输入：

- `测试数据/person2/outputs/person2_pytorchsim_transformer.csv`

输出：

- `results/flood_cycle_sim_v1/person2_gemm/workload_summary.csv`
- `results/flood_cycle_sim_v1/person2_gemm/system_intervals.csv`
- `results/flood_cycle_sim_v1/person2_gemm/value_check_summary.csv`

结果：

- rows: 30
- MAC-only FLOOD faster than PyTorchSim: 9
- MAC-only FLOOD slower than PyTorchSim: 21
- MAC-only average speedup: 0.7826x
- MAC-only max speedup: 2.5291x
- MAC-only min speedup: 0.1357x
- system-projection FLOOD faster than PyTorchSim: 0
- system-projection average speedup: 0.1124x
- value_check_status: missing_evidence

严格结论：person2 这批 GEMM 不适合作为 FLOOD 主优势图；它更适合作为 baseline 交叉检查或反例审查材料。

加入系统层后，这个结论更强：如果把 DMA/配置开销以当前保守模型串行加入，person2 这批 GEMM 没有任何一条比 PyTorchSim baseline 更快。因此论文不能用这批 GEMM 证明 FLOOD 全芯片性能优势。

## 下一步必须补齐

1. 用 direct full-chip RTL 或 testbench 校准 DMA/配置阶段，而不是只用接口宽度估计。
2. 为 direct RTL blocked 样本保留独立输出，不允许进入 plot-ready 主表。
3. 接入真实 workload 的 golden 输出和 RTL 输出，使 `value_check_status` 从 `missing_evidence` 变成 pass/fail。
4. 增加 softmax/稀疏/跳零/outlier 的机制开关，但在没有 RTL 证据前默认 `unsupported`。
5. 增加 CI/回归入口：每次修改 simulator 后自动跑 `rtl_validation` 和 `value_checker_smoke`，要求周期 6/6 pass，checker pass/fail 均正确。
