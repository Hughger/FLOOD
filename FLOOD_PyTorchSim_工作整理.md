# FLOOD 与 PyTorchSim 实验工作整理

更新时间：2026-07-01

## 1. 当前目标

本阶段目标不是直接跑完整大模型 RTL，而是建立一条可复现的实验链路：

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

换句话说：PyTorchSim 用来提供 workload 和 baseline，FLOOD RTL 用来校准真实性，RTL-aware / calibrated model 用来扩展到完整 workload。

## 2. 服务器与远程环境

当前服务器：

```text
ssh -p 30659 root@connect.westc.seetacloud.com
```

本地私钥：

```text
D:\work-yanjiusheng\HPCA\codex_ssh_keys3\seetacloud_ed25519_codex_tmp
```

远程工作目录：

```text
/root/autodl-tmp/torchsim_work/flood_rtl_calibration
```

远程已确认可用工具：

```text
iverilog
vvp
python3
```

远程已生成/使用的关键文件：

```text
generated/MacMachineWrapper.v
src/test/verilog/testbench_r32c32t16.v
run/calib_01.vvp
run/calib_01_zeroinit.vvp
make_simple_hex.py
```

其中 `run/calib_01_zeroinit.vvp` 是目前主要使用的 RTL 仿真版本。它通过 Verilog 宏把生成 RTL 中的随机寄存器初始化固定为 0，避免 `x` 未知态污染 `doneInterrupt`。

## 3. FLOOD RTL 调试进展

使用的 FLOOD RTL 顶层：

```text
D:\work-yanjiusheng\FLOOD\e203_asic_c\e203_asic_c\flood_accelerator\rtl\e203\subsys\mac_unit\MacMachineWrapper.v
```

已完成的 RTL 调试：

1. 确认 `MacMachineWrapper.v` 可以用 Icarus Verilog 编译。
2. 修正 testbench 配置地址：

```text
0x42: global config
0x43: run process
0x44: interrupt clear
```

3. 发现原始仿真存在 `x` 未知态污染：

```text
doneInterruptReg = x
outDoneFire = x
```

4. 通过全 0 初始化版本解决：

```text
iverilog -DRANDOMIZE_REG_INIT -DRANDOM=32\'h0 ...
```

5. 最小用例已经稳定完成：

```text
k=1, cout=1, group_size=4, cin_idx_total=1 -> 35 cycles
```

## 4. 当前已完成的 RTL 实测

目前完整 RTL 校准集包含 22 个完成用例。

覆盖范围：

```text
k: 1, 3
cout: 1, 2, 4, 8, 10, 16, 32
group_size: 2, 4, 8, 16
cin_idx_total: 1, 2, 4, 10
res_cols/res_rows: 1 或 2
```

代表性结果：

| 用例 | RTL cycles |
|---|---:|
| `k=1, cout=1, group=4, cin=1` | 35 |
| `k=1, cout=2, group=4, cin=1` | 48 |
| `k=3, cout=1, group=4, cin=1` | 79 |
| `k=3, cout=2, group=4, cin=1` | 133 |
| `k=1, cout=32, group=4, cin=1` | 438 |
| `k=3, cout=8, group=4, cin=1` | 457 |
| `k=1, cout=10, group=4, cin=10` | 1493 |
| `k=3, cout=10, group=4, cin=10` | 5623 |

中等 spatial conv 验证结果：

```text
k=3, cout=10, group_size=4, cin_idx_total=10
cycles = 562;562;562;562;562;562;562;562;562;565
total = 5623
```

这说明当前 RTL 行为中，多 Cin 基本是线性重复：

```text
total = (cin_idx_total - 1) * nonfinal_run + final_run
```

## 5. RTL 校准公式

当前 bring-up calibration 使用的 final run 周期公式：

```text
cycles =
  35
  + 13 * (cout - 1)
  + 22 * (k - 1)
  + 20.5 * (k - 1) * (cout - 1)
  + 1.5 * max(group_size - 4, 0)
  + 0.375 * max(group_size - 8, 0)
  + 2.75 * (k - 1) * max(group_size - 4, 0)
```

多 Cin 情况：

```text
nonfinal_run = final_run - 3
total_per_spatial = (cin_idx_total - 1) * nonfinal_run + final_run
```

多空间块情况：

```text
total = total_per_spatial * res_cols * res_rows
```

当前 22 个完整 RTL case 上：

```text
mean_abs_error_percent = 0.0
max_abs_error_percent = 0.0
```

注意：这个 0% 表示当前公式能解释已有 22 个 bring-up 点，不代表已经完成论文级泛化验证。

## 6. 已生成的本地脚本

脚本目录：

```text
D:\work-yanjiusheng\HPCA\flood_local
```

关键脚本：

| 脚本 | 作用 |
|---|---|
| `flood_rtl_aware_model.py` | FLOOD 结构感知估算模型 |
| `flood_backend_pipeline.py` | 将 PyTorchSim workload 转成 FLOOD backend 结果包 |
| `flood_paper_compare.py` | 生成不同 paper-level scenario 对比 |
| `prepare_rtl_calibration.py` | 准备 RTL 校准源码与运行矩阵 |
| `calibrate_rtl_smoke.py` | 根据 RTL 实测 CSV 生成 bring-up 校准报告 |
| `apply_rtl_bringup_calibration.py` | 将 RTL bring-up 校准公式外推到 workload 层级 |
| `flood_calibration_report.py` | 根据填入的 RTL 周期生成模型误差报告 |
| `make_pytorchsim_workload_from_trace.py` | 从 trace/workload 生成 PyTorchSim 输入 |
| `summarize_*` 系列 | 汇总 PyTorchSim/TOGSim/FLOOD 结果 |

## 7. 已生成的主要结果目录

总结果目录：

```text
D:\work-yanjiusheng\HPCA\results\flood_pytorchsim_backend_v1
```

### 7.1 原始 FLOOD backend 估算

```text
flood_current_rtl_backend_details.csv
flood_current_rtl_backend_summary.csv
flood_backend_scenario_details.csv
flood_backend_scenario_summary.csv
```

说明：

- `flood_current_rtl_backend_*` 是早期 RTL-aware analytical model 结果。
- `flood_backend_scenario_*` 是不同假设场景下的 paper-level projection，例如 `flood_main`、`flood_conservative`、`flood_aggressive`。

### 7.2 RTL 校准源码包

```text
rtl_calibration_src
rtl_calibration_src.tar.gz
```

包含：

```text
src/main/scala/...       FLOOD Scala 源码片段
src/test/verilog/...     testbench、dpSRAM 等
make_simple_hex.py       生成特征和权重 hex
rtl_calibration_run_matrix.csv
```

### 7.3 RTL 原始校准结果

```text
rtl_calibration_results
```

重要文件：

| 文件 | 内容 |
|---|---|
| `rtl_smoke_matrix_zeroinit_summary.csv` | 第一批 smoke RTL case |
| `rtl_validation_matrix_zeroinit.csv` | 第二批验证 case |
| `rtl_spatial_validation_zeroinit.csv` | 空间块重复验证 |
| `rtl_largecout_validation_zeroinit.csv` | 大 cout 验证 |
| `rtl_mid_complete_zeroinit.csv` | 中等 spatial conv 完整验证 |
| `rtl_bringup_all_with_mid_complete_zeroinit.csv` | 合并后的完整 bring-up 数据 |
| `README_mid_validation.md` | 中等验证说明 |

### 7.4 最新 RTL bring-up 校准报告

```text
rtl_bringup_calibration_v3
```

重要文件：

```text
README.md
rtl_smoke_calibration_details.csv
rtl_smoke_calibration_summary.csv
```

这是当前最完整的 RTL 校准报告，包含 22 个完整 case。

### 7.5 workload 级 RTL bring-up 外推

```text
rtl_bringup_workload_v1
```

重要文件：

```text
README.md
rtl_bringup_workload_details.csv
rtl_bringup_workload_summary.csv
```

该目录把 22 个 RTL bring-up case 得到的校准公式外推到 workload 层级。

当前 workload 外推结果显示 FLOOD 在当前 RTL 行为下较慢，尤其 spatial conv：

| dataset | operator | workmode | PyTorchSim cycles | calibrated FLOOD cycles | speedup |
|---|---|---|---:|---:|---:|
| `synthetic_unet_trace` | conv | pointwise_conv | 6442 | 22080 | 0.291757 |
| `synthetic_unet_trace` | conv | spatial_conv | 35075 | 704144 | 0.049812 |
| `synthetic_unet_trace` | gemm | gemm | 20875 | 80054 | 0.260761 |
| `workload_v1` | conv | spatial_conv | 665734 | 42600432 | 0.015627 |
| `workload_v1` | gemm | gemm | 95217 | 1051808 | 0.090527 |

注意：这不是最终论文结论，而是根据当前 RTL testbench 行为得到的外推结果，用于指导下一步实验。

## 8. 当前可以支持的论文表述

目前可以较稳妥地写：

```text
We built a FLOOD RTL bring-up flow based on MacMachineWrapper.v and validated
22 small-to-mid kernels using Icarus Verilog. The RTL measurements were used
to calibrate an RTL-aware workload projection model.
```

中文意思：

```text
我们基于 FLOOD 的 MacMachineWrapper RTL 建立了可运行的 RTL bring-up 流程，
并用 Icarus Verilog 完成了 22 个小到中等规模 kernel 的周期验证。
这些 RTL 实测点被用于校准 RTL-aware workload projection 模型。
```

目前不建议直接写：

```text
FLOOD 在完整 workload 上已经通过 RTL 仿真验证。
```

因为还没有完整大层级 RTL 长跑结果。

## 9. 当前结论

1. FLOOD RTL 可以跑通并产出周期。
2. `MacMachineWrapper.v` 的 testbench 地址和初始化问题已经修复。
3. 当前 RTL 行为比早期乐观模型慢很多。
4. 多 Cin run 的周期规律已经在 `cin=10` 中等 case 上得到验证。
5. workload 级 projection 可以生成，但仍属于 calibrated projection，不是完整 RTL 论文主结果。
6. 下一步应迁移到 Verilator 或商业仿真器，或选择少数代表层做长时间 RTL 验证。

## 10. 下一步建议

### 10.1 短期

1. 将当前 Icarus Verilog 流程迁移到 Verilator。
2. 选择 2-3 个代表性 workload layer 做完整 RTL 验证：

```text
pointwise conv / GEMM: 1-2 个
spatial conv k=3: 1-2 个
attention GEMM: 1 个
```

3. 生成一张 `RTL measured vs calibrated model` 误差表。

### 10.2 中期

1. 让多人用 PyTorchSim 跑更多 workload。
2. 统一收集格式：

```text
operator, shape_args, total_cycles, latency_us, utilization, memory traffic
```

3. 用 `apply_rtl_bringup_calibration.py` 统一换算成 FLOOD calibrated projection。
4. 根据 projection 结果挑选最值得 RTL 验证的层。

### 10.3 论文材料建议

论文中可以组织成三类表：

1. PyTorchSim baseline workload 表。
2. FLOOD RTL representative validation 表。
3. RTL-calibrated full workload projection 表。

这样比单纯依赖 analytical model 更可信，也比尝试完整 RTL 跑完整模型更现实。

