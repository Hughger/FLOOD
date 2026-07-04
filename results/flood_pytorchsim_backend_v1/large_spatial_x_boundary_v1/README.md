# FLOOD large-spatial X boundary v1

## 结论

为了最快收紧 HPCA 论文数据边界，本目录记录 `k=1, cout=2, cin=2` 下空间长度扩大的直接 RTL 结果：

- `spatial=16` 的 workload 行已 direct RTL-clean。
- `spatial=64` 的 `trace_gemm_007` 周期完全匹配 6976，但 XPROBE2 显示 `cluster_x=256, router_read_x=127, router_write_x=256, output_read_x=8319`。

因此当前 `k=1, cin>=2, spatial_points>=64` 不应进入主性能表，应作为 D 级 large-spatial RTL debug 边界。

## 快速推进策略

后续不再逐条长跑同类 large-spatial k1 行；除非先修复 RTL 输出有效性，否则这类行只能作为 blocked/boundary 证据。
