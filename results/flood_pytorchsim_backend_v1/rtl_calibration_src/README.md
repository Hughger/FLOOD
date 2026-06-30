# FLOOD RTL Calibration Source Package

This is a minimal package for generating `MacMachineWrapper.v` and running small RTL calibration cases.

Expected flow on Linux:

```bash
sbt "runMain FLOOD_Accelerator.GenerateVerilog"
python3 src/test/verilog/generate_test_data.py --row-size 32 --col-size 32 --k 1 --cout 2 --cin-idx-total 1 --group-size 4 --group-num 4 --res-rows 1 --res-cols 1
iverilog -g2012 -o run/calib_01.vvp generated/MacMachineWrapper.v src/test/verilog/dpSRAM.v src/test/verilog/testbench_r32c32t16.v
vvp run/calib_01.vvp +K=1 +COUT=2 +GROUP_SIZE=4 +CIN_IDX_TOTAL=1 +RES_COLS=1 +RES_ROWS=1
```

`rtl_calibration_run_matrix.csv` contains the bounded cases derived from PyTorchSim workload rows.
