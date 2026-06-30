# RTL Bring-up Calibrated FLOOD Workload Estimate

This applies the 21-case Icarus Verilog bring-up calibration to workload-level PyTorchSim rows.

Important: this is an extrapolated estimate, not final paper evidence. It should guide the next RTL runs.

| dataset | op | workmode | rows | PyTorchSim cycles | calibrated FLOOD cycles | speedup |
|---|---|---|---:|---:|---:|---:|
| synthetic_unet_trace | conv | pointwise_conv | 4 | 6442.0 | 22080.0 | 0.291757 |
| synthetic_unet_trace | conv | spatial_conv | 7 | 35075.0 | 704144.0 | 0.049812 |
| synthetic_unet_trace | gemm | gemm | 10 | 20875.0 | 80054.0 | 0.260761 |
| workload_v1 | conv | spatial_conv | 4 | 665734.0 | 42600432.0 | 0.015627 |
| workload_v1 | gemm | gemm | 4 | 95217.0 | 1051808.0 | 0.090527 |

Use this table to choose representative larger RTL validation layers next.
