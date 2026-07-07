# FLOOD System Calibration Batch

Manifest: `results\flood_cycle_sim_v1\system_calibration_batch_templates\system_calibration_smoke_manifest.csv`

This batch turns full-chip RTL/testbench logs into measured phase-cycle rows,
then checks them against the simulator system model.

Generated files:

- `calibration_batch_status.csv`: parse/check command status.
- `merged_parsed_system_calibration.csv`: log-derived measured phase cycles.
- `merged_system_calibration_summary.csv`: pass/mismatch counts.
- `merged_system_calibration_details.csv`: per-row phase errors.
- `calibration_readiness_summary.csv`: paper system-timing gate.

Main-figure rule: use system timing only when `paper_system_timing_policy` is
`ready_for_main_figure_system_timing`.
