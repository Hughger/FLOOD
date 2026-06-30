# FLOOD RTL Calibration Preparation

These cases are derived from PyTorchSim workload rows but intentionally bounded for fast RTL simulation.

## Recommended Existing RTL Entry

- Testbench: `FLOOD/src/test/verilog/testbench_r32c32t16.v`
- Helper SRAM: `FLOOD/src/test/verilog/dpSRAM.v`
- Generated DUT: `MacMachineWrapper.v` from Chisel `GenerateVerilog`

## Generated Cases

| Case | Op | Workmode | Shape | RTL args |
|---|---|---|---|---|
| calib_01 | gemm | gemm | `1 256 64` | `+K=1 +COUT=2 +GROUP_SIZE=4 +CIN_IDX_TOTAL=2 +RES_COLS=1 +RES_ROWS=1` |
| calib_02 | gemm | gemm | `256 64 512` | `+K=1 +COUT=8 +GROUP_SIZE=4 +CIN_IDX_TOTAL=1 +RES_COLS=4 +RES_ROWS=1` |
| calib_03 | gemm | gemm | `256 768 3072` | `+K=1 +COUT=8 +GROUP_SIZE=4 +CIN_IDX_TOTAL=6 +RES_COLS=4 +RES_ROWS=1` |
| calib_04 | conv | pointwise_conv | `1 16 16 64 64 1 1 0` | `+K=1 +COUT=2 +GROUP_SIZE=4 +CIN_IDX_TOTAL=1 +RES_COLS=1 +RES_ROWS=4` |
| calib_05 | conv | pointwise_conv | `1 32 32 64 64 1 1 0` | `+K=1 +COUT=2 +GROUP_SIZE=4 +CIN_IDX_TOTAL=1 +RES_COLS=1 +RES_ROWS=4` |
| calib_06 | conv | pointwise_conv | `1 32 32 128 64 1 1 0` | `+K=1 +COUT=2 +GROUP_SIZE=4 +CIN_IDX_TOTAL=1 +RES_COLS=1 +RES_ROWS=4` |
| calib_07 | conv | spatial_conv | `1 32 32 64 64 3 2 1` | `+K=3 +COUT=2 +GROUP_SIZE=4 +CIN_IDX_TOTAL=1 +RES_COLS=1 +RES_ROWS=4` |
| calib_08 | conv | spatial_conv | `1 32 32 64 64 3 1 1` | `+K=3 +COUT=2 +GROUP_SIZE=4 +CIN_IDX_TOTAL=1 +RES_COLS=1 +RES_ROWS=4` |
| calib_09 | conv | spatial_conv | `1 64 64 320 320 3 1 1` | `+K=3 +COUT=8 +GROUP_SIZE=4 +CIN_IDX_TOTAL=3 +RES_COLS=2 +RES_ROWS=4` |
| calib_10 | conv | spatial_conv | `1 32 32 640 640 3 1 1` | `+K=3 +COUT=8 +GROUP_SIZE=4 +CIN_IDX_TOTAL=5 +RES_COLS=1 +RES_ROWS=4` |

## Next Step

Compile the existing testbench with the matching `iverilog_defines`, run with `runtime_plusargs`, then parse `[INTR] done` time and SRAM/NoC counters from the log. Fill `rtl_sim_cycles` in the original calibration table.
