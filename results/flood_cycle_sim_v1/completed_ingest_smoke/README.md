# FLOOD Completed RTL Task Ingest

Inputs:

- task CSV: `results\flood_cycle_sim_v1\completed_ingest_smoke_inputs\task_manifest.csv`
- system manifest: `results\flood_cycle_sim_v1\completed_ingest_smoke_inputs\system_manifest.csv`
- value manifest: `results\flood_cycle_sim_v1\completed_ingest_smoke_inputs\value_manifest.csv`
- paper gate manifest: `results\flood_cycle_sim_v1\completed_ingest_smoke_inputs\paper_gate_manifest.csv`

This directory is the postprocessor path for finished student/server RTL runs.
It checks that completed task files are real, parses full-chip timing logs,
checks numeric outputs, merges evidence into the final paper gate, and exports
only rows approved for main figures.

Generated files:

- `ingest_run_status.csv`: command status for each stage.
- `manifest_check/`: path and required-marker readiness check.
- `system_batch/`: full-chip/system timing gate.
- `value_batch/`: golden-vs-RTL numeric gate.
- `final_gate/`: workload/value/system merged paper gate.
- `main_figure_export/`: CSVs allowed for plotting.
