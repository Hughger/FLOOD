# k3 spatial probe v1

## 结论

为了快速增强 HPCA 支撑证据，本目录补了两个小规模 k3 空间重复 RTL 探针：

- `k=3, cout=2, cin=2, res_cols=2, res_rows=1`
- `k=3, cout=2, cin=2, res_cols=1, res_rows=2`
- `k=3, cout=2, cin=2, res_cols=2, res_rows=2`
- `k=3, cout=2, cin=2, res_cols=2, res_rows=4`

前两个探针均完成 4 次 run，cycle list 均为 `329;332;329;332`，总周期 1322，X 计数为 0。第三个探针完成 8 次 run，cycle list 为 `329;332` 重复 4 次，总周期 2644，X 计数为 0。第四个探针完成 16 次 run，cycle list 为 `329;332` 重复 8 次，总周期 5288，X 计数为 0。

## 可信度影响

这把 k3 证据从原来的 `res=1` 扩展到 `spatial_points=2` 的横向和纵向重复，并进一步扩展到 `spatial_points=4/8` 的二维重复。它不能直接证明 `spatial=64` 的 workload 行可进主表，但能更有力地支撑 k3 projection 作为 appendix 证据，而不是完全无空间重复证据。

## 使用边界

当前 HPCA 主性能表仍只允许 direct workload clean 行。k3 workload 行在没有 exact workload RTL-clean 前，只能进入 appendix/projection。
