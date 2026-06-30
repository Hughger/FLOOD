# FLOOD RTL Smoke Calibration

This report uses completed Icarus Verilog runs of `MacMachineWrapper.v`.

## Current Equation

For a final run:

`cycles = 35 + 13*(cout-1) + 22*(k-1) + 20.5*(k-1)*(cout-1) + 1.5*max(group_size-4,0) + 0.375*max(group_size-8,0) + 2.75*(k-1)*max(group_size-4,0)`

For multi-Cin cases, each non-final run currently uses `final_run_cycles - 3`.

## Fit Quality

- cases: 22
- mean absolute error: 0.0%
- max absolute error: 0.0%

## How To Use

- Use this only as a bring-up calibration for the FLOOD RTL path.
- Do not use it as final paper evidence until larger RTL cases are run.
- Next useful cases: larger `cout`, larger `cin_idx_total`, `res_cols/res_rows > 1`, and representative workload layers.

## Raw Cases

| case | measured | predicted | error % |
|---|---:|---:|---:|
| c01_k1_c1_g4_ci1 | 35 | 35.0 | 0.0 |
| c02_k1_c2_g4_ci1 | 48 | 48.0 | 0.0 |
| c03_k3_c1_g4_ci1 | 79 | 79.0 | 0.0 |
| c04_k3_c2_g4_ci1 | 133 | 133.0 | 0.0 |
| c05_k1_c1_g8_ci1 | 41 | 41.0 | 0.0 |
| c06_k1_c1_g4_ci2 | 67 | 67.0 | 0.0 |
| v01_k1_c4_g4_ci1 | 74 | 74.0 | 0.0 |
| v02_k1_c8_g4_ci1 | 126 | 126.0 | 0.0 |
| v03_k3_c4_g4_ci1 | 241 | 241.0 | 0.0 |
| v04_k1_c1_g2_ci1 | 35 | 35.0 | 0.0 |
| v05_k1_c1_g16_ci1 | 56 | 56.0 | 0.0 |
| v06_k3_c1_g8_ci1 | 107 | 107.0 | 0.0 |
| v07_k1_c1_g4_ci4 | 131 | 131.0 | 0.0 |
| v08_k1_c2_g4_ci2 | 93 | 93.0 | 0.0 |
| s01_k1_c1_g4_ci1_rc2_rr1 | 70 | 70.0 | 0.0 |
| s02_k1_c1_g4_ci1_rc1_rr2 | 70 | 70.0 | 0.0 |
| s03_k1_c1_g4_ci1_rc2_rr2 | 140 | 140.0 | 0.0 |
| s04_k3_c1_g4_ci1_rc2_rr1 | 158 | 158.0 | 0.0 |
| l01_k1_c16_g4_ci1 | 230 | 230.0 | 0.0 |
| l02_k1_c32_g4_ci1 | 438 | 438.0 | 0.0 |
| l03_k3_c8_g4_ci1 | 457 | 457.0 | 0.0 |
| m02_k3_c10_g4_ci10_complete | 5623 | 5623.0 | 0.0 |
