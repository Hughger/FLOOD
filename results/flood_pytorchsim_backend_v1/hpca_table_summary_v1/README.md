# HPCA table summary v1

## Main Table

| scope | rows | PyTorchSim cycles | FLOOD cycles | speedup |
|---|---:|---:|---:|---:|
| direct RTL-clean only | 6 | 6450.0000 | 6689.0000 | 0.964270 |

Main-table claim: all rows are direct RTL-clean and XPROBE-clean. No C/D rows are included.

## Appendix Projection

| scope | rows | PyTorchSim cycles | FLOOD projected cycles | ratio |
|---|---:|---:|---:|---:|
| k3 projection only | 11 | 700809.0000 | 116271232.0000 | 0.006027 |

Appendix claim: projection rows are not main performance evidence. They are labeled as calibrated projections.

## Excluded / Blocked

- blocked/excluded rows: 14
- reason: direct blocked, XPROBE boundary, unsupported operator, or known extrapolation boundary.

## Paper wording

Use: The main performance table reports only direct RTL-clean workload rows. Additional k3 results are reported separately as calibrated projections with explicit scope limits.

Avoid: The full workload is RTL validated; all projection rows are equivalent to direct RTL measurements.
