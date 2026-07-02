# FLOOD RTL Group16 Spatial Calibration v6

## 目的

本报告把 `group_size=16` 的空间重复路径拆成可进入论文数据的区域和仍需 debug 的区域。v6 只接纳 `k=1, cin_idx_total=1, res_cols<=2` 且无 X 的 RTL 样本。

## v6 规则

对 `k=1/group_size=16/cin_idx_total=1/res_cols<=2`：

```text
first_col = 19*cout + 18
repeat_col = 56
total = first_col + (res_cols-1)*repeat_col
```

## 验证结果

| split | total | clean candidates | blocked | mean abs err % | max abs err % |
|---|---:|---:|---:|---:|---:|
| fit | 3 | 3 | 0 | 0.0 | 0.0 |
| holdout | 4 | 4 | 0 | 0.0 | 0.0 |
| blocked | 7 | 0 | 7 | 0.0 | 0.0 |

## 关键结论

- fitting 样本：`cout=6/12/16, res_cols=2`，全部无 X，v6 误差 0%。
- holdout 样本：`cout=4/8/10/14, res_cols=2`，全部无 X，v6 误差 0%。
- `res_cols=3/4` 样本仍有 X，探针显示 X 出现在 Cluster 输出侧，应继续作为 RTL debug 阻塞项。

## 论文使用建议

可以把 `group16/k1/cin1/res_cols<=2` 标为 RTL-clean calibration/holdout evidence。`res_cols>=3` 必须单独列为未通过 RTL 验证的边界，不应混入论文主性能表。
