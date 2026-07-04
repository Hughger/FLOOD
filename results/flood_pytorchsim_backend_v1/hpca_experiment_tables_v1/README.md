# HPCA experiment tables v1

This directory is the current paper-data production output. It maps existing PyTorchSim/FLOOD data into the E1-E9 tables from the HPCA test plan.

## One-command generation

Run the full paper-data pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File flood_local\run_hpca_paper_data_pipeline.ps1
```

Regenerate only these final E1-E9 tables from existing gates:

```powershell
powershell -ExecutionPolicy Bypass -File flood_local\run_hpca_experiment_tables.ps1
```

## Generated tables

- `E1_end_to_end_main_results.csv`
- `E2_sparsity_proxy.csv`
- `E3_quantization_proxy.csv`
- `E4_outlier_proxy.csv`
- `E5_softmax_proxy.csv`
- `E6_dataflow_storage.csv`
- `E7_ablation_proxy.csv`
- `E8_diffusion_family.csv`
- `E9_baseline_fairness.csv`
- `table_audit.csv`

## Rule

Values are generated only when the current toolchain has the data. Unknown paper metrics are marked MISSING rather than guessed.
Use `table_audit.csv` after each run to see which tables still contain MISSING/proxy values.

## Current proxy tables

- `E2_sparsity_proxy.csv` is generated from synthetic sparsity assumptions and workload MAC/cycle counts. It has the final table schema, but final paper values should replace proxy sparsity with measured activation/weight sparsity.
- `E3_quantization_proxy.csv` estimates latency and peak-memory scaling from bit width. Quality metrics remain MISSING until the quantization quality runner is integrated.
- `E4_outlier_proxy.csv` estimates outlier bypass overhead from configured outlier ratios. Quality recovery remains MISSING until outlier quality experiments are integrated.
- `E5_softmax_proxy.csv` estimates softmax latency and approximation error from vector length. It must be replaced by an RTL/numerical softmax runner for final paper claims.
- `E7_ablation_proxy.csv` reuses E2/E3/E4/E5 proxies and current dataflow labels to produce a complete ablation-table skeleton. Final paper values require measured integrated runners.

## How others should use it

1. Update the upstream workload CSVs or run new experiments.
2. Run `flood_local/run_hpca_paper_data_pipeline.ps1`.
3. Fill paper tables only from the generated E1-E9 CSV files.
