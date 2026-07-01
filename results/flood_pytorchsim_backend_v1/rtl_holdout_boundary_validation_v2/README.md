# FLOOD RTL 留出验证报告 v1

## 目的

这份报告只使用没有参与公式拟合的 RTL 小样本，用来检查当前 RTL-aware 公式是否真的能外推。它的价值不是证明模型已经完成，而是把可信和不可信的边界说清楚。

## 当前公式

`final_run = 35 + 13*(cout-1) + 22*(k-1) + 20.5*(k-1)*(cout-1) + 1.5*max(group_size-4,0) + 0.375*max(group_size-8,0) + 2.75*(k-1)*max(group_size-4,0)`

多 Cin 情况下，非最后一次 run 暂按 `final_run - 3` 估计。

## 总体结果

- 总样本数：14
- 有效样本数：12
- 异常/无效样本数：2
- 完全命中样本数：3
- 有效样本平均绝对误差：11.9657%
- 有效样本最大绝对误差：24.9226%

## 结论

- 当前公式在 `group_size=4`、`k=1/group_size=8`、多 Cin、多空间点以及部分较大 `cout` 组合上可以完全命中 RTL。
- `h02_k3_c4_g8_ci2` 暴露了 `k>1` 与 `group_size=8` 的交互项不足，说明卷积核尺寸和 group 并行度不能继续简单相加。
- 当前公式在 `group_size=16` 且 `cout` 增大时开始低估周期，说明高 group 边界还需要补充 RTL 样本和公式项。
- `h04_k1_c6_g16_ci4` 出现后续 run 为 0 的现象，暂判为 testbench/中断清除边界问题，不能作为性能数据使用。

## 有效样本明细

| case | measured | predicted | error cycles | error % | note |
|---|---:|---:|---:|---:|---|
| h01_k1_c12_g4_ci3_rc2 | 1056 | 1056.0 | 0.0 | 0.0 | exact |
| h02_k3_c4_g8_ci2 | 673 | 535.0 | -138.0 | -20.5052 | model gap |
| h03_k3_c16_g4_ci1 | 889 | 889.0 | 0.0 | 0.0 | exact |
| h05_k1_c6_g16_ci1 | 132 | 121.0 | -11.0 | -8.3333 | model gap |
| h06_k1_c6_g8_ci4 | 415 | 415.0 | 0.0 | 0.0 | exact |
| h07_k1_c8_g16_ci1 | 170 | 147.0 | -23.0 | -13.5294 | model gap |
| b01_k3_c2_g8_ci1 | 184 | 161.0 | -23.0 | -12.5 | model gap |
| b02_k3_c4_g8_ci1 | 338 | 269.0 | -69.0 | -20.4142 | model gap |
| b03_k3_c8_g8_ci1 | 646 | 485.0 | -161.0 | -24.9226 | model gap |
| b04_k1_c2_g16_ci1 | 56 | 69.0 | 13.0 | 23.2143 | model gap |
| b05_k1_c4_g16_ci1 | 94 | 95.0 | 1.0 | 1.0638 | model gap |
| b06_k1_c12_g16_ci1 | 246 | 199.0 | -47.0 | -19.1057 | model gap |

## 异常样本

| case | measured cycle_list | reason |
|---|---|---|
| h04_k1_c6_g16_ci4 | `129;0;0;0` | zero or negative cycle count observed |
| b07_k1_c6_g16_ci2 | `129;0` | zero or negative cycle count observed |

## 下一步

为了把数据推进到论文级，下一批 RTL 应重点覆盖 `group_size=16` 下 `cout=2/4/6/8/12/16`、`cin_idx_total=1/2/4`，同时补齐 `k=3/group_size=8` 的交互样本，并修复多 Cin 的 done/interrupt 清除问题。
