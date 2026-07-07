# FLOOD Main Figure Export Audit

Final gate: `results\flood_cycle_sim_v1\final_paper_gate_smoke\final_paper_data_gate.csv`
Export directory: `results\flood_cycle_sim_v1\main_figure_export_smoke`

This audit is adversarial: it treats the final gate as authoritative and checks
whether `main_figure_rows.csv`, `rejected_rows.csv`, and `export_summary.csv`
could have leaked unapproved rows into paper plots.
