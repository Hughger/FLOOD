# FLOOD spatial multi-Cin X boundary v1

## 目的

本目录记录 `k=1/group_size=16/res_cols=2/res_rows=8` 下的多 Cin 空间重复边界。这个边界用于防止 simulator 只看 cycle count，而忽略 RTL 输出有效性。

## 结论

- `cin=2, spatial=16` 已有直接 workload clean 样本，XPROBE 全 0。
- `cin=3, spatial=16` 的边界探针 48 次 run 全部完成，cycle count 为 2592，符合模型预期，但 XPROBE 显示 Cluster/Router/Output 侧 X。
- `cin=4` 与 `cin=8` 的真实 workload 行也都出现 cycle match 但 XPROBE blocked。
- `trace_gemm_008` 说明小空间 `spatial=5` 但很深 Cin 的行同样会出现 cycle match 但 XPROBE blocked。
- 因此当前 `k=1, cin>=3, spatial_points>=16` 不应进入论文主性能表，应作为 D 级 RTL debug 边界。
  对 `cin=24`，即使 `spatial_points=5` 也已经观察到 D 级阻塞。

## 论文使用规则

可以使用 clean 行说明周期模型在小范围内有效；不能把 `cin>=3, spatial=16` 的行作为 FLOOD 可用性能数据。即使 cycle count 与 simulator 预测一致，也必须同时满足 XPROBE clean。
