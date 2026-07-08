# FLOOD Value Check Batch

Manifest: `results\flood_cycle_sim_v1\rtl_value_repeat_prepare\value_repeat_manifest.csv`

This batch compares golden numeric outputs with RTL/testbench numeric outputs.
The checker is format-light: it extracts numeric tokens and compares them with
the requested tolerances.

Generated files:

- `value_batch_status.csv`: whether each checker run executed.
- `merged_value_check_summary.csv`: combined pass/fail/missing status.
- `merged_value_check_details.csv`: mismatching numeric positions when present.
- `value_readiness_summary.csv`: paper value-correctness gate.

Main-figure rule: use a workload only when `main_value_ready_policy` is
`ready_for_main_figure_value`.
