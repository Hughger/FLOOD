# Independent Golden Feasibility Audit

This audit separates repeatability evidence from independent correctness
evidence. Current RTL repeat runs are useful because they show the same inputs
produce identical timing and output files across runs.

They are still not enough for direct paper value correctness. The missing piece
is an independent Python golden model that exactly reproduces:

- `features.hex` and `weights_ping.hex` packing.
- `drive_feature_from_files` address mapping.
- `planeWorkMode` stateful accumulation.
- Output SRAM and Joint SRAM dump semantics.

Until that model exists and passes value checks, calibrated RTL projections
remain review/calibration data, not final main-figure paper rows.
