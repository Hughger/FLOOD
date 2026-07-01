# FLOOD RTL 高 group 重复执行修复验证 v1

## 目的

之前 `group_size=16` 在重复 run 时会出现后续 run 为 0，例如：

- `h04_k1_c6_g16_ci4`: `129;0;0;0`
- `b07_k1_c6_g16_ci2`: `129;0`
- `u06_k1_c12_g16_rc2`: `246;0`

本轮目标是验证 testbench 侧的清中断/等待策略是否能消除 0 周期。

## 修复思路

定位日志发现：第一次 run 报 done 后，输出 SRAM 仍有后续写入，随后 done 可能再次拉高。原 testbench 立即清中断并进入下一次配置，导致下一次 run 一开始就看到旧 done。

修复策略：

1. 每次 run 前先清 done/error。
2. 清完后等待 `intr_done/intr_error` 和内部 done valid 降低。
3. 每次 run 结束后不立即清中断，先等待较长 drain gap，让后续输出写入和 done pulse 完成。
4. drain 后再清中断，并确认中断线降回 0。

## 修复后结果

| case | 参数 | 修复前 | 修复后 | X count | 判断 |
|---|---|---:|---:|---:|---|
| `f01_k1_c6_g16_ci2_fixed` | `k=1, cout=6, group=16, cin=2` | `129;0` | `129;56` | 0 | 0 周期已消除 |
| `f02_k1_c6_g16_ci3_fixed` | `k=1, cout=6, group=16, cin=3` | 未测 | `129;53;56` | 0 | 多 Cin 可继续校准 |
| `f03_k1_c6_g16_ci4_fixed` | `k=1, cout=6, group=16, cin=4` | `129;0;0;0` | `129;53;53;56` | 0 | 多 Cin 可继续校准 |
| `f04_k1_c12_g16_rc2_fixed` | `k=1, cout=12, group=16, res_cols=2` | `246;0` | `246;56` | 396 | 空间重复仍无效 |

## 当前结论

- `group_size=16` 多 Cin 的 0 周期问题主要来自 testbench 清中断过早，已通过 drain-before-clear 方式消除。
- 修复后多 Cin 样本没有 X，说明该路径可以进入下一轮 RTL 校准。
- `group_size=16` 的空间重复路径仍有大量 X，即使第二次 run 不再是 0，也不能作为论文性能数据。
- 因此，下一步应把多 Cin 纳入 v5 校准，但空间重复仍要单独排查。

## 对 v4/v5 模型的影响

v4 对 `group_size=16` 的单次 run 拟合较好，但之前不能覆盖高 group 多 Cin。修复后观测到：

- first Cin: `129` cycles
- middle Cin: `53` cycles
- final Cin: `56` cycles

这说明 `group_size=16` 的多 Cin 不能继续沿用简单的 `final-3` 规则。更合理的 v5 方向是：

```text
group16 first run = single-run cycles
group16 middle run ≈ 53 cycles
group16 final run ≈ 56 cycles
```

该规则还需要更多 `cout=2/4/8/12/16` 的多 Cin 样本验证。

## 下一步

1. 对 `group_size=16, cin_idx_total=2/4` 补 `cout=2/4/8/12/16`。
2. 拟合 v5 高 group 多 Cin 项。
3. 单独排查 `res_cols/res_rows>1` 的空间重复 X 问题。
4. 在论文数据中，将高 group 多 Cin 与高 group 空间重复分开标注可信度。
