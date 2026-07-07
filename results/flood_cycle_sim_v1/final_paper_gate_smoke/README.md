# FLOOD Final Paper Data Gate

Manifest: `results\flood_cycle_sim_v1\final_paper_gate_templates\final_paper_gate_smoke_manifest.csv`

This gate merges three independent checks:

1. workload timing/paper-use gate
2. output value-correctness gate
3. full-chip/system timing calibration gate

Generated files:

- `final_paper_data_gate.csv`: one row per planned paper data row.
- `final_paper_data_summary.csv`: compact ready/not-ready count.
- `evidence_manifest.csv`: source/output file sizes and SHA256 hashes.

Main-figure rule: only rows with `final_paper_data_policy=ready_for_main_figure`
may enter main paper figures.
