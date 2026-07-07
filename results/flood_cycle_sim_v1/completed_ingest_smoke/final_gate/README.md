# FLOOD Final Paper Data Gate

Manifest: `results\flood_cycle_sim_v1\completed_ingest_smoke_inputs\paper_gate_manifest.csv`

This gate merges three independent checks:

1. workload timing/paper-use gate
2. output value-correctness gate
3. full-chip/system timing calibration gate

Generated files:

- `final_paper_data_gate.csv`: one row per planned paper data row.
- `final_paper_data_summary.csv`: compact ready/not-ready count.
- `evidence_manifest.csv`: source/output file sizes and SHA256 hashes.

Hardware source signature: `566baa5411b356ed67c5572fb2231e100a1fa8e53bf07504edf503c7a1573108`

Main-figure rule: only rows with `final_paper_data_policy=ready_for_main_figure`
may enter main paper figures.
