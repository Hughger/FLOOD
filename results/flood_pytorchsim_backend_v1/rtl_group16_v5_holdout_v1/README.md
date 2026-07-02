# FLOOD RTL Group16 Multi-Cin v5 独立验证 v1

## 目的

这份报告使用没有参与 v5 拟合的新 RTL 样本，验证 `group_size=16` 多 Cin 校准规则是否能够外推。

## 验证样本

这些点避开了 v5 拟合使用的 `cout=2/4/6/8/12/16` 与 `cin=2/4` 组合，改用：

- `cout=10, cin=3`
- `cout=10, cin=5`
- `cout=14, cin=3`
- `cout=14, cin=5`

所有样本：

- `k=1`
- `group_size=16`
- `group_num=1`
- `res_cols=res_rows=1`
- `x_count=0`
- 无 0 周期 run

## v5 规则

```text
first_run = 19*cout + 15
middle_run = 53
final_run = 56
total = first_run + max(cin_idx_total-2, 0)*middle_run + final_run
```

## 误差对比

| 指标 | v4 | v5 |
|---|---:|---:|
| 有效样本数 | 4 | 4 |
| 平均绝对误差 | 135.5928% | 0.0% |
| 最大绝对误差 | 183.871% | 0.0% |

## 明细

| case | measured | cycles | v4 pred | v4 err % | v5 pred | v5 err % |
|---|---:|---|---:|---:|---:|---:|
| `h16_c10_ci3_fixed` | 314 | `205;53;56` | 618.0 | 96.8153 | 314.0 | 0.0 |
| `h16_c10_ci5_fixed` | 420 | `205;53;53;53;56` | 1028.0 | 144.7619 | 420.0 | 0.0 |
| `h16_c14_ci3_fixed` | 390 | `281;53;56` | 846.0 | 116.9231 | 390.0 | 0.0 |
| `h16_c14_ci5_fixed` | 496 | `281;53;53;53;56` | 1408.0 | 183.871 | 496.0 | 0.0 |

## 结论

v5 不只是拟合训练点，在未参与拟合的 `cout=10/14`、`cin=3/5` 上也完全命中。  
因此，`group_size=16` 多 Cin 的 RTL-aware v5 校准可信度明显高于 v4。

仍需保留限制：`res_cols/res_rows>1` 的空间重复路径仍有 X 问题，不能与本报告的多 Cin 路径混为同一可信度等级。
