# FLOOD Paper Workload Batch

Manifest: `results\flood_cycle_sim_v1\batch_templates\batch_smoke_manifest.csv`

Generated files:

- `batch_run_status.csv`: whether each workload ran.
- `merged_workload_summary.csv`: combined per-layer/workload cycle summaries.
- `merged_paper_gate.csv`: combined confidence grades and paper-use policies.
- `merged_value_check_summary.csv`: combined value-check status.
- `batch_readiness_summary.csv`: one row per workload for handoff review.

Rule for use: students may run this batch tool, but only rows passing the paper
gate and later value/system evidence checks should enter main paper figures.
