# FLOOD Cycle Simulator v1 对抗性审查

## 当前结论

`flood_local/flood_cycle_sim.py` 当前是一个分层的 cycle-interval simulator，不是完整芯片级 RTL 替代品。

它现在可以做三类事：

1. 对 Base FLOOD MAC datapath 的 GEMM/Conv workload 给出周期区间。
2. 对系统层 CPU config + DMA + MAC 阶段给出可校准的投影区间。
3. 对 standalone SoftmaxModule 给出受门禁保护的周期投影。

所有输出都带 `confidence_grade` 和 `paper_use_policy`，目的就是防止把投影数据、blocked RTL 数据和 direct RTL-clean 数据混在一起画论文主图。

## 已验证证据

当前直接 RTL-clean 周期验证结果：

- direct RTL-clean cases: 6
- passed cases: 6
- failed cases: 0
- direct RTL blocked cases: 5
- blocked cases with X: 5
- blocked cases with zero-cycle behavior: 1
- pass rate: 100%
- max absolute cycle error: 0

权威输出文件：

- `results/flood_cycle_sim_v1/rtl_validation/rtl_validation_summary.csv`
- `results/flood_cycle_sim_v1/rtl_validation/rtl_validation_details.csv`
- `results/flood_cycle_sim_v1/rtl_validation/rtl_blocked_cases.csv`

## 可以主张什么

可以主张：

1. 当前 simulator 对已覆盖的 Base FLOOD MAC run timing 能逐区间复现 RTL-clean 样本。
2. 对支持范围内的 GEMM、k=1 Conv、k=3 Conv，可以输出周期区间、总周期、330MHz 延迟和相对 PyTorchSim baseline 的速度比。
3. 每条 workload 都带证据等级，可以自动区分 main-table candidate、appendix projection 和 exclude rows。
4. 工具已经具备 full-chip RTL/testbench 校准入口：真实 RTL 只要输出阶段周期，就能进入 `--system-calibration` gate。
5. 工具已经具备 output-value checker 入口：提供 golden/RTL 数值文件后，可以检查输出数值是否通过。
6. 六个优化目录已经进入 inventory 和机制门禁；没有证据前默认不进入主性能模型。

## 不能主张什么

不能主张：

1. 当前已经是完整芯片级 cycle-accurate simulator。
2. 当前已经完整覆盖 CPU 控制流、DMA、AXI、SRAM 数据正确性和软件调度。
3. 当前真实 workload 的输出值已经全部通过 RTL 数值正确性验证。
4. 当前 softmax、稀疏、跳零、outlier、INT8/INT4、channel-group sparsity 已经都有主表级证据。
5. C 级 projection 或 D 级 blocked/invalid 样本可以进入 HPCA 主性能图。

## 机制材料清单

用户提供的六个机制目录已经由 `flood_local/build_mechanism_inventory.py` 扫描：

- `mactree/`
- `outlier/`
- `INT8-INT4/`
- `softmax/`
- `zero-skip/`
- `channel group sparisy/`

输出文件：

- `results/flood_cycle_sim_v1/mechanism_inventory/mechanism_summary.csv`
- `results/flood_cycle_sim_v1/mechanism_inventory/mechanism_changed_files.csv`
- `results/flood_cycle_sim_v1/mechanism_inventory/mechanism_sim_hooks.csv`
- `results/flood_cycle_sim_v1/mechanism_inventory/mechanism_enable_template.csv`

严格结论：这些目录是完整工程副本或机制材料，不是干净 patch。任何机制启用前都必须补齐 timing/value/quality 证据。

## Softmax 投影模型

本轮新增 standalone softmax 周期模型，依据：

- `softmax/flood/SoftmaxModule.scala`
- `softmax/flood/SoftmaxModule时序.md`

可确认规则：

- `vector_dim_cfg` 必须是 32 的整数倍，否则 `dim_err`。
- `n = vector_dim_cfg / 32`。
- 状态机范围为 `0 ~ 5n+24`。
- 单个向量周期数按 `5n+25` 计。

当前 simulator 使用的公式：

```text
softmax_cycles_per_vector = 5 * (vector_dim / 32) + 25
total_cycles = num_vectors * softmax_cycles_per_vector
```

smoke workload：

- `softmax_vec_32`: 30 cycles
- `softmax_vec_128`: 45 cycles
- `softmax_attn_4x64`: 140 cycles
- `softmax_invalid_33`: excluded, `unsupported_softmax_dim`

输出目录：

- `results/flood_cycle_sim_v1/softmax_smoke/`

证据等级：

- 合法 softmax 行：`C_softmax_standalone_chisel_projection`
- 非 32 倍数维度：`D_softmax_invalid_dimension`

严格结论：softmax 现在可以批量跑投影数据，但不能进入论文主性能表。它最多作为 appendix/projection 或设计趋势图，除非后续完成 integrated full-chip RTL-clean timing 和输出值验证。

## MACTree 结构剖面

本轮新增 `flood_local/build_mactree_profile.py`，用于从 base FLOOD 和 `mactree/` 材料中自动抽取 MAC 树结构差异。

输出目录：

- `results/flood_cycle_sim_v1/mactree_profile/`

关键结果：

- base `pipeline=2`
- mactree `pipeline=3`
- base `tLatency=4`
- mactree `tLatency=4`
- base `compressionFactor=4`
- mactree `compressionFactor=4`
- mactree 新增 `add_skip_en=true.B`
- `CIMcore.scala` 中 mactree 侧出现更多 `MACTreeFlood`、`stageRegistersOut`，并出现 `wZero || aZero` 跳零相关逻辑

门禁结果：

- `confidence_grade=D_mactree_timing_not_validated`
- `paper_use_policy=exclude_from_main_performance_tables`
- `simulator_status=profile_only_not_enabled`

严格结论：mactree 当前不能直接作为“MAC 树更快”的论文数据。它混合了流水线结构变化和跳零相关逻辑，必须先做 RTL/testbench 周期验证和输出值验证；如果要主张功耗优势，还需要 activity counters。当前工具只把它纳入结构剖面和证据门禁，不让它影响主性能周期。

## Zero-Skip 与 Channel-Group Sparsity 剖面

本轮新增 `flood_local/build_sparsity_profiles.py`，用于审查：

- `zero-skip/flood`
- `channel group sparisy/flood`

输出目录：

- `results/flood_cycle_sim_v1/sparsity_profiles/`

自动抽取结果：

- 两个目录都出现 `activation_zero_flags`
- 两个目录都出现 `weight_zero_flags`
- 两个目录都有 `zero_or_condition` 相关源码证据
- 两个目录的 `groupSize` / `groupNum` 出现次数都高于 base
- 两个目录没有提供可直接用于 workload 的稀疏率输入表
- 两个目录没有提供可直接用于主性能表的 RTL-clean timing/value gate

门禁结果：

- `zero_skip`: `D_zero_skip_timing_not_validated`
- `channel_group_sparsity`: `D_channel_group_sparsity_timing_not_validated`
- 两者均为 `exclude_from_main_performance_tables`

严格结论：zero-skip 和 channel-group sparsity 现在已经进入工具链证据清单，但不能影响周期结果。要让它们进入论文主图，至少还缺三类证据：逐 workload 稀疏率、RTL/testbench 周期测量、输出值正确性。若主张功耗/能效，还必须补 activity counters 或门级功耗测量。

## INT8/INT4 与 Outlier 剖面

本轮新增 `flood_local/build_quant_outlier_profiles.py`，用于审查：

- `INT8-INT4/flood`
- `outlier/flood`

输出目录：

- `results/flood_cycle_sim_v1/quant_outlier_profiles/`

自动抽取结果：

- `INT8-INT4` 检测到更多量化模块、量化参数、INT8/INT4 相关材料
- `outlier` 检测到更多量化模块、INT4 相关材料，并额外检测到 outlier 相关材料
- 两个目录都没有提供可直接绑定到 workload 的量化配置表
- 两个目录都没有提供主表级 accuracy/error 结果
- 两个目录都没有提供 full-chip 或 direct RTL-clean timing gate

门禁结果：

- `int8_int4`: `D_int8_int4_quality_timing_not_validated`
- `outlier`: `D_outlier_quality_timing_not_validated`
- 两者均为 `exclude_from_main_performance_tables`

严格结论：量化和 outlier 机制不能只凭“源码里出现 INT4/量化/outlier”就进入论文图。它们需要同时满足两类证据：性能证据和质量证据。性能证据至少要有 RTL/testbench 周期；质量证据至少要有每个 workload 的误差/精度/图像质量指标，并且输出值检查不能失败。

## person2 GEMM 审查

学生 person2 GEMM 数据适合做交叉检查，不适合做 FLOOD 优势主图。

当前结论：

- MAC-only FLOOD faster than PyTorchSim: 9
- MAC-only FLOOD slower than PyTorchSim: 21
- MAC-only average speedup: 0.7826x
- system-projection FLOOD faster than PyTorchSim: 0
- value_check_status: missing_evidence

严格结论：这批 GEMM 不能证明 FLOOD 整体优于 PyTorchSim NPU。

## 论文主数据升级条件

某一类数据要进入 HPCA 主图，至少需要同时满足：

1. 对应 workload 的 `sim_status=ok`。
2. 周期证据为 direct RTL-clean，或 full-chip RTL/testbench 校准通过。
3. blocked-X、zero-cycle、invalid-dim 样本必须排除。
4. 如果主张数值正确性，需要 `value_check_status=pass`。
5. 如果使用系统层周期，需要 `system_calibration_summary.csv` 中目标范围 `measured_rows>0` 且 `mismatch_rows=0`。
6. 如果使用机制优化，需要说明该机制来自哪个目录、启用了哪些规则、哪些数据仍是 projection。

## 下一步最短路径

最快提升可信度的顺序：

1. 继续把六个机制逐个接成“默认关闭、证据驱动开启”的 simulator hook。
2. 优先接入 softmax 的输出值检查，因为它已有独立模块和明确时序。
3. 对 mactree/zero-skip/outlier/INT8-INT4/channel-group sparsity 先做 inventory-to-model mapping，不急着宣称主图。
4. 在服务器上跑最小 RTL/testbench 校准样本，把真实 measured cycle 回填到 `--system-calibration`。
5. 只有通过 gate 的行才交给学生批量跑；学生只负责重复运行和收集表格，不负责判断能不能进论文。

## Simulator Readiness 自动审查

本轮新增 `flood_local/build_simulator_readiness_report.py`，并已接入
`flood_local/run_flood_cycle_sim.ps1`。每次完整回归后会自动生成：

- `results/flood_cycle_sim_v1/readiness_report/readiness_requirements.csv`
- `results/flood_cycle_sim_v1/readiness_report/readiness_summary.csv`
- `results/flood_cycle_sim_v1/readiness_report/README.md`

当前严格审查结果：

- strict pass: 8 / 13
- strict pass percent: 61.54%
- usable with caveats: 73.08%
- goal status: `not_complete_for_hpca_paper_data`
- main blocker: real workload value checks and full-chip/system timing calibration

严格结论：工具已经能稳定地产生带证据等级和论文使用策略的 CSV，
也已经把六个优化目录纳入 inventory 和 gate；本轮还新增了 manifest batch runner，
可以让学生按清单批量运行并得到合并后的 gated CSV。但还不能交给学生直接批量跑出
HPCA 主图数据。原因不是批量脚本不能跑，而是主图级数据还缺两类硬证据：

1. 真实 workload 的 RTL/golden 输出数值检查。
2. CPU/DMA/control/full-chip 阶段周期的真实校准，且 `mismatch_rows=0`。

因此当前最安全说法仍然是：

- 已完成 Base FLOOD MAC datapath 的 direct RTL-clean 周期锚点。
- 已完成机制目录的自动盘点和论文闸门。
- 已完成学生批量运行入口、合并表和主图 readiness 标记。
- 未完成完整 cycle-accurate chip simulator。
- 未完成可直接支撑 HPCA 主图的全 workload 数据链。

新增批量入口：

- `flood_local/run_paper_workload_batch.py`
- `results/flood_cycle_sim_v1/batch_templates/paper_workload_manifest_template.csv`
- `results/flood_cycle_sim_v1/batch_templates/batch_smoke_manifest.csv`
- `results/flood_cycle_sim_v1/batch_smoke/batch_readiness_summary.csv`

当前 smoke 结果中，`synthetic_unet_trace` 和 `softmax_smoke` 都能批量跑通，
并生成合并表；但 `main_figure_ready_policy` 均为 `not_ready_for_main_figure`。
这正是想要的行为：学生可以跑，工具会把不够主图证据等级的数据挡住。

## Full-Chip/System Calibration Batch

本轮新增系统校准批量入口：

- `flood_local/run_system_calibration_batch.py`
- `results/flood_cycle_sim_v1/system_calibration_batch_templates/system_calibration_manifest_template.csv`
- `results/flood_cycle_sim_v1/system_calibration_batch_templates/system_calibration_smoke_manifest.csv`
- `results/flood_cycle_sim_v1/system_calibration_batch_smoke/calibration_readiness_summary.csv`

它的作用是把 full-chip RTL/testbench 日志中的阶段周期 marker 批量解析出来，
再统一送入 `flood_cycle_sim.py --system-calibration` 检查。

当前 smoke 结果：

- calibration id: `log_parse_smoke`
- measured rows: 1
- mismatch rows: 0
- policy: `ready_for_main_figure_system_timing`

严格解释：这证明“系统校准通路”已经打通，也证明工具能识别一条干净的
full-chip timing 样本。但这不等于真实论文 workload 已经完成 full-chip 校准。
真实 workload 仍然必须提供对应 RTL/testbench 日志，并通过：

1. `measured_rows > 0`
2. `mismatch_rows = 0`
3. `missing_measurement_rows = 0`
4. `error_rows = 0`

只有满足这些条件的 workload，系统层周期才可以进入主图候选。

## Value Check Batch

本轮新增输出数值检查批量入口：

- `flood_local/run_value_check_batch.py`
- `results/flood_cycle_sim_v1/value_check_batch_templates/value_check_manifest_template.csv`
- `results/flood_cycle_sim_v1/value_check_batch_templates/value_check_smoke_manifest.csv`
- `results/flood_cycle_sim_v1/value_check_batch_smoke/value_readiness_summary.csv`

它的作用是把每个 workload 的 golden 数值输出和 RTL/testbench 数值输出成对比较，
并生成 `main_value_ready_policy`。

当前 smoke 结果：

- `value_pass_smoke`: `ready_for_main_figure_value`
- `value_fail_smoke`: `not_ready_for_main_figure`

严格解释：这证明批量数值检查通路可以同时放行正确结果、拦截错误结果。
但这仍不代表真实论文 workload 已经通过数值正确性验证。真实 workload 必须提供：

1. golden numeric output
2. RTL/testbench numeric output
3. 合理的 `rtol/atol`
4. `value_check_status=pass`

否则即使周期数据能跑出来，也只能作为 timing/projection 审查材料，不能作为主图级完整实验数据。

## Final Paper Data Gate

本轮新增最终论文数据闸门：

- `flood_local/build_paper_data_gate.py`
- `results/flood_cycle_sim_v1/final_paper_gate_templates/final_paper_gate_manifest_template.csv`
- `results/flood_cycle_sim_v1/final_paper_gate_templates/final_paper_gate_smoke_manifest.csv`
- `results/flood_cycle_sim_v1/final_paper_gate_smoke/final_paper_data_gate.csv`
- `results/flood_cycle_sim_v1/final_paper_gate_smoke/evidence_manifest.csv`

它把三类证据合并到同一行：

1. workload timing / paper-use gate
2. output value-correctness gate
3. full-chip/system timing calibration gate

最终只看一个字段：

```text
final_paper_data_policy
```

当前 smoke 结果：

- paper rows: 2
- ready for main figure: 0
- not ready for main figure: 2

严格解释：这是正确行为。当前 smoke 中即使存在 value pass 和 system pass，
只要 workload timing 本身仍是 projection 或没有主图候选行，最终 gate 仍然会阻止进入主图。

后续交给学生批量跑时，原则应改为：

- 学生负责按 manifest 跑 workload/value/system 三类数据。
- 我们只认 `final_paper_data_gate.csv`。
- 只有 `final_paper_data_policy=ready_for_main_figure` 的行才能进入主图。
- 其它行可以作为 appendix、debug 或补证据任务，但不能直接画主图。

本轮进一步给 final gate 增加了 `evidence_manifest.csv`。它记录：

- 输入 manifest
- workload gate
- value gate
- system gate
- final gate 输出表
- final summary 输出表

每个文件都会记录路径、是否存在、文件大小和 SHA256。这样后续如果某张图的数据被质疑，
可以直接回查该行 final gate 使用的是哪一版输入表，避免“手动搬表搬错”。

## Main Figure Export Package

本轮新增主图数据包导出器：

- `flood_local/export_main_figure_package.py`
- `results/flood_cycle_sim_v1/main_figure_export_smoke/main_figure_rows.csv`
- `results/flood_cycle_sim_v1/main_figure_export_smoke/rejected_rows.csv`
- `results/flood_cycle_sim_v1/main_figure_export_smoke/export_summary.csv`

它只导出：

```text
final_paper_data_policy=ready_for_main_figure
```

当前 smoke 结果：

- exported main figure rows: 0
- rejected rows: 2

严格解释：这是正确行为。当前没有任何 smoke 行达到主图级证据，所以
`main_figure_rows.csv` 应该为空。后续画图脚本应只读取这个导出包，
不能直接读取 workload summary、projection table 或中间 gate 表。

## Timeline Consistency Gate

本轮新增周期时间线一致性审查：

- `flood_local/build_timeline_consistency_report.py`
- `results/flood_cycle_sim_v1/timeline_consistency/timeline_checks.csv`
- `results/flood_cycle_sim_v1/timeline_consistency/timeline_summary.csv`

检查内容：

1. `duration_cycles >= 0`
2. `end_cycle_exclusive - start_cycle = duration_cycles`
3. 同一 workload 内 interval 连续，不出现空洞或重叠
4. interval 末尾周期与 `workload_summary.csv` 中的总周期一致

严格解释：这只能证明 simulator 输出的时间线账目自洽，不能证明 RTL 行为正确。
但如果这一步失败，后续所有批量数据都不应该使用，因为周期表本身已经不可信。
