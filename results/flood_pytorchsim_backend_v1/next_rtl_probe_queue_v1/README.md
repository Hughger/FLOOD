# 下一批最短 RTL 探针队列 v1

## 目的

本队列用于继续推进 HPCA 测试方案，同时避免盲目跑完整大 workload。排序原则是：优先选择能最快改变 B/C/D 分级或补强 appendix 可信度的短探针。

## 队列

| 优先级 | case | 参数 | 目的 | 预计结论价值 |
|---:|---|---|---|---|
| P0 | `k3_c2_ci2_spatial16` | `k=3, cout=2, cin=2, res_cols=2, res_rows=8` | 把 k3 spatial clean 链从 1/2/4/8 推到 16 | 若 clean，可支撑最小 k3 workload 的空间外推更接近真实层 |
| P0 | `k3_c2_ci18_spatial1` | `k=3, cout=2, cin=18, res_cols=1, res_rows=1` | 检查 k3 大 Cin 是否立即 X 或周期失配 | 若 blocked，可解释多数 k3 workload 仍只能 appendix |
| P1 | `k3_c2_ci2_spatial32` | `k=3, cout=2, cin=2, res_cols=2, res_rows=16` | 继续逼近 `spatial=64` 的最小 k3 workload | 耗时更长，建议在 spatial16 clean 后再跑 |
| P1 | `k3_c2_ci18_spatial2` | `k=3, cout=2, cin=18, res_cols=2, res_rows=1` | 同时测试 k3 大 Cin + 小空间重复 | 可定位 k3 workload 的主要阻塞来自 Cin 还是 spatial |
| P2 | `softmax_minimal_vector` | vector length 32/64 | 决定 E5 是实现、近似还是明确 excluded | 需要 RTL/模型入口，不是当前 MacMachine testbench 直接可跑 |

## 当前建议

下一步先跑 `k3_c2_ci2_spatial16`。如果 clean，就把 k3 spatial appendix 证据链推进到 16；如果 blocked，就能立刻确定 k3 空间边界在 8 到 16 之间。
