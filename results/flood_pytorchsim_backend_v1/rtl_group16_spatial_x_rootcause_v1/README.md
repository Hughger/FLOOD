# FLOOD group16 空间重复 X 根因定位

## 结论

本次定位的是 `group_size=16, res_cols=2` 空间重复 case 中第二个空间列输出变成 X 的问题。

关键结论：

- 重新生成输入后，`features.hex` 为 `512` 行、每行 `128` 个 hex 字符，输入宽度正确。
- 探针确认 `feature_data` 没有 X，`weight ping` 读取也没有 X。
- `Cluster` 输出 NoC 没有 X，说明 MAC/Cluster 侧不是第一污染源。
- `OutRouterPlanePost` 在第二个空间列会读取 output SRAM 的高地址 `513..523`。
- 这些高地址在当前 testbench SRAM 模型中此前没有写过，因此读出 X；Router 随后把 X 合并后写回 output SRAM 地址 `0..11`。
- 将 testbench SRAM memory 初始清零后，同一个 case 的 X 计数降为 `0`，周期仍为 `246;56`。

因此，当前问题更像是仿真 memory 初始化/软件预清零约束没有建模完整，而不是 FLOOD 计算阵列直接产生错误。

## 核心证据

| probe | case | cycles | x_count | 关键观察 |
|---|---|---:|---:|---|
| input_rerun | `k=1, cout=12, group=16, cin=1, res_cols=2` | `246;56` | 396 | 输入重新生成后仍有 X，排除旧输入文件问题 |
| xprobe | 同上 | `246;56` | 408 | `feat_x=0, wping_x=0, oping_x=12` |
| xprobe2 | 同上 | `246;56` | 419 | `cluster_x=0, router_read_x=11, router_write_x=12`，Router 读取 output SRAM `513..523` 为 X |
| memclear_xprobe2 | 同上，SRAM memory 初始清零 | `246;56` | 0 | `cluster_x=0, router_read_x=0, router_write_x=0` |

## 对论文数据的影响

这条证据把之前的边界条件从“`group16` 空间重复 RTL 不可信”推进到更具体的说法：

```text
group16 空间重复路径的计算与周期可以跑通；
当前 X 来自 output buffer 读未初始化地址；
在采用明确的 output SRAM 清零 precondition 后，该 case 可得到无 X RTL 周期。
```

但在正式论文中，仍建议谨慎表述：

- 可以把该结果作为 `RTL debug/root-cause evidence`。
- 若要把 `group16/res_cols>1` 纳入论文性能表，应先把“output SRAM 预清零”写成明确实验前置条件，并补跑更多代表性空间重复样本。
- 不应只凭单个 memclear case 就声称完整 workload RTL validation 已完成。

## 下一步

1. 用 memclear testbench 补跑 `group_size=16` 的空间重复矩阵，例如 `cout=6/12/16`、`res_cols=2/4`。
2. 比较 memclear 前后周期是否一致，确认清零只影响 X，不改变控制时序。
3. 将无 X 的空间重复样本加入 v5/v6 校准集，再更新 workload projection。
