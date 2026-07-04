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
- `E3_quantization_missing.csv`
- `E4_outlier_missing.csv`
- `E5_softmax_missing.csv`
- `E6_dataflow_storage.csv`
- `E7_ablation_proxy.csv`
- `E8_diffusion_family.csv`
- `E9_baseline_fairness.csv`

## Rule

Values are generated only when the current toolchain has the data. Unknown paper metrics are marked MISSING rather than guessed.

## Current proxy tables

- `E2_sparsity_proxy.csv` is generated from synthetic sparsity assumptions and workload MAC/cycle counts. It has the final table schema, but final paper values should replace proxy sparsity with measured activation/weight sparsity.
- `E7_ablation_proxy.csv` reuses the E2 proxy to produce Base/+zero skipping/+adder pruning/+GCSE rows. Quant/outlier/softmax/dataflow/full-system rows remain MISSING until their runners are integrated.

## How others should use it

1. Update the upstream workload CSVs or run new experiments.
2. Run `flood_local/run_hpca_paper_data_pipeline.ps1`.
3. Fill paper tables only from the generated E1-E9 CSV files.
