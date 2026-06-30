# FLOOD RTL Smoke Calibration

This report uses completed Icarus Verilog runs of `MacMachineWrapper.v`.

## Current Equation

For a final run:

`cycles = 35 + 13*(cout-1) + 22*(k-1) + 20.5*(k-1)*(cout-1) + 1.5*(group_size-4)`

For multi-Cin cases, each non-final run currently uses `final_run_cycles - 3`.

## Fit Quality

- cases: 6
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
