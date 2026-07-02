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

## memclear 矩阵补测

补测文件：

```text
memclear_matrix_v1.csv
memclear_holdout_v1.csv
```

补测范围：

```text
k=1
group_size=16
cin_idx_total=1
res_rows=1
cout=6/12/16
res_cols=2/4
```

结果：

| case | cycles | x_count | probe 结论 |
|---|---:|---:|---|
| `cout=6, res_cols=2` | `132;56` | 0 | 清零后无 X |
| `cout=12, res_cols=2` | `246;56` | 0 | 清零后无 X |
| `cout=16, res_cols=2` | `322;56` | 0 | 清零后无 X |
| `cout=6, res_cols=4` | `132;56;56;56` | 420 | 仍有 X，且 `cluster_x=12` |
| `cout=12, res_cols=4` | `246;56;56;56` | 824 | 仍有 X，且 `cluster_x=24` |
| `cout=16, res_cols=4` | `322;56;56;56` | 1088 | 仍有 X，且 `cluster_x=32` |

这说明：

- `res_cols=2` 的 X 可以由 output SRAM 初始清零解决。
- `res_cols=4` 仍有更深层问题；此时 Router 不再读取 X，但 Cluster 输出已经出现 X。
- 因此当前可把 `group16/res_cols=2` 作为下一批候选 RTL 校准样本；`group16/res_cols>=4` 仍应列为阻塞项。

后续 holdout 补测进一步确认：

- `cout=4/8/10/14, res_cols=2` 全部无 X。
- `cout=4/8/10/14, res_cols=3` 全部有 Cluster 输出 X。
- 因此边界更准确地收敛为：`res_cols<=2` 可进入 v6 候选，`res_cols>=3` 暂列为 blocked。

## 对论文数据的影响

这条证据把之前的边界条件从“`group16` 空间重复 RTL 不可信”推进到更具体的说法：

```text
group16 空间重复路径的计算与周期可以跑通；
当前 X 来自 output buffer 读未初始化地址；
在采用明确的 output SRAM 清零 precondition 后，res_cols=2 case 可得到无 X RTL 周期；
res_cols=4 仍需要继续定位 Cluster 内部状态污染。
```

但在正式论文中，仍建议谨慎表述：

- 可以把该结果作为 `RTL debug/root-cause evidence`。
- 若要把 `group16/res_cols>1` 纳入论文性能表，应先把“output SRAM 预清零”写成明确实验前置条件，并补跑更多代表性空间重复样本。
- 不应只凭单个 memclear case 就声称完整 workload RTL validation 已完成。

## 下一步

1. 将 `res_cols=2` 的无 X 样本加入下一版 v6 校准候选集。
2. 对 `res_cols=4` 加更细粒度 Cluster 探针，定位是第 3/4 空间列的 feature pingpong、内部累加器还是 NoC 状态污染。
3. 在 v6 里把 `res_cols=2` 和 `res_cols>=4` 分开建模，避免把未验证区域混入论文主表。
