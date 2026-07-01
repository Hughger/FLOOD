# FLOOD RTL 高 group 重复执行异常记录 v1

## 背景

在 v4 独立验证中，`group_size=16` 的单次 run 可以稳定得到周期并被 v4 命中，但一旦同一仿真中执行第二次 run，会出现第二次 run 立即 done、周期为 0 的现象。

这个问题会影响：

- `group_size=16` 且 `cin_idx_total>1`
- `group_size=16` 且 `res_cols/res_rows>1`
- 任何需要重复触发 run 的真实 layer RTL 验证

因此它是把 v4 推进到论文级 RTL 验证前必须解决的阻塞项。

## 已观察样本

| case | 参数 | 结果 | 状态 |
|---|---|---|---|
| `h04_k1_c6_g16_ci4` | `k=1, cout=6, group=16, cin=4` | `129;0;0;0` | invalid |
| `b07_k1_c6_g16_ci2` | `k=1, cout=6, group=16, cin=2` | `129;0` | invalid |
| `u06_k1_c12_g16_rc2` | `k=1, cout=12, group=16, res_cols=2` | `246;0` | invalid |

对照样本：

| case | 参数 | 结果 | 状态 |
|---|---|---|---|
| `u03_k3_c6_g8_ci2` | `k=3, cout=6, group=8, cin=2` | `489;492` | valid |

说明：重复执行本身不是普遍坏掉，问题集中在 `group_size=16`。

## 日志证据

`u06_k1_c12_g16_rc2.log` 中的关键顺序：

```text
[TB] Special config: cinIdx=0 resolutionColIdx=0 workMode=0 ... => 0x00000000
[TB] Trigger run at time 220300
[TB] Done interrupt after 246 cycles at time 269900

[TB] Special config: cinIdx=0 resolutionColIdx=1 workMode=4 ... => 0x00002040
[TB] Trigger run at time 629900
[TB] Done interrupt after 0 cycles at time 630300
```

随后日志中出现大量输出 SRAM 未知值：

```text
[OWR] ping addr=0 data=0xxxxxxxx...
DEBUG: oping_rdata=0xxxxxxxx..., signed_data=x
```

`u03_k3_c6_g8_ci2.log` 中的对照顺序：

```text
[TB] Special config: cinIdx=0 resolutionColIdx=0 workMode=0 ... => 0x00000000
[TB] Trigger run ...
[TB] Done interrupt after 489 cycles ...

[TB] Special config: cinIdx=1 resolutionColIdx=0 workMode=3 ... => 0x00001801
[TB] Trigger run ...
[TB] Done interrupt after 492 cycles ...
```

## 初步判断

这不像是周期统计脚本错误，而更像是 testbench 或控制寄存器流程问题：

- 第二次 run 刚触发就 done，说明 done/interrupt 或 busy 状态可能没有被正确清除。
- 第二次 run 后输出 SRAM 大量为 X，说明内部读写状态或输出 SRAM 状态没有进入有效计算路径。
- 问题集中在 `group_size=16`，且在 `cin` 重复和空间重复两种路径都能复现。
- `group_size=8` 的多 Cin 对照样本正常，说明重复 run 的基本 testbench 框架不是完全错误。

## 建议排查顺序

1. 在 testbench 中每次 run 前显式清 done/interrupt，并等待 busy/idle 状态完成一次稳定切换。
2. 对比 `workMode=3` 和 `workMode=4` 的特殊配置含义，确认 `resolutionColIdx>0` 时是否需要额外清输出 SRAM 或切换 ping/pong。
3. 在第二次 run 前后打印核心控制寄存器、done、busy、输出 SRAM 写使能。
4. 对 `group_size=16` 的重复 run 做最小复现：
   - `k=1, cout=2, group=16, cin=2`
   - `k=1, cout=2, group=16, res_cols=2`
5. 修复后重新跑 v4 独立验证中的 `u06`，再补 `cin_idx_total=2/4` 和 `res_cols/res_rows=2` 的样本。

## 对论文数据的影响

在该问题修复前：

- `group_size=16` 的单次 run 样本可以用于 v4 小规模校准。
- `group_size=16` 的多 Cin、多空间点样本不能作为论文性能数据。
- workload 级结果中涉及高 group 重复执行的部分只能标注为 calibrated projection，不能声称已经完成 RTL validation。
