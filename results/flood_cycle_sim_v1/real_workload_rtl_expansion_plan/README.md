# Real Workload RTL Expansion Plan

This plan expands the first server RTL subset run without pretending it is
already paper data.

Priority meaning:

- P0: clean/reduced convolution tiles that should complete and improve timing calibration.
- P1: larger tiles that may still timeout but can collect more clean cycle markers.
- P2: no-output GEMM/1x1 paths that need separate testbench bring-up before use.

Rows remain calibration or bring-up only until full-layer/full-chip timing and
golden value checks are available.
