# FLOOD Main Figure Export Audit

Final gate: `results\flood_cycle_sim_v1\adversarial_export_inputs\final_gate.csv`
Export directory: `results\flood_cycle_sim_v1\adversarial_export_inputs`

This audit is adversarial: it treats the final gate as authoritative and checks
whether `main_figure_rows.csv`, `rejected_rows.csv`, and `export_summary.csv`
could have leaked unapproved rows into paper plots.
