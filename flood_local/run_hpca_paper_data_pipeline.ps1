param(
  [string]$OutDir = "results\flood_pytorchsim_backend_v1\hpca_experiment_tables_v1"
)

$ErrorActionPreference = "Stop"
$Python = "C:\Users\98676\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $Python)) {
  $Python = "python"
}

& $Python flood_local\apply_group16_v7_workload.py `
  --input results\flood_pytorchsim_backend_v1\group16_v5_workload_v1\group16_v5_workload_details.csv `
  --out-dir results\flood_pytorchsim_backend_v1\group16_v7_workload_v1

& $Python flood_local\build_paper_data_readiness.py `
  --workload results\flood_pytorchsim_backend_v1\group16_v7_workload_v1\group16_v7_workload_details.csv `
  --multicin-summary results\flood_pytorchsim_backend_v1\rtl_group16_multicin_v5\rtl_group16_multicin_v5_summary.csv `
  --multicin-holdout-summary results\flood_pytorchsim_backend_v1\rtl_group16_v5_holdout_v1\rtl_group16_multicin_v5_summary.csv `
  --spatial-summary results\flood_pytorchsim_backend_v1\rtl_group16_spatial_v6\rtl_group16_spatial_v6_summary.csv `
  --k3-summary results\flood_pytorchsim_backend_v1\rtl_group16_k3_v7\rtl_group16_k3_v7_summary.csv `
  --out-dir results\flood_pytorchsim_backend_v1\paper_data_readiness_v1

& $Python flood_local\build_hpca_submission_gate.py `
  --readiness results\flood_pytorchsim_backend_v1\paper_data_readiness_v1\paper_workload_readiness_details.csv `
  --out-dir results\flood_pytorchsim_backend_v1\hpca_submission_gate_v1

& $Python flood_local\build_k3_projection_gate.py `
  --workload results\flood_pytorchsim_backend_v1\group16_v7_workload_v1\group16_v7_workload_details.csv `
  --out-dir results\flood_pytorchsim_backend_v1\k3_projection_gate_v1

& $Python flood_local\build_hpca_table_summary.py `
  --gate-dir results\flood_pytorchsim_backend_v1\hpca_submission_gate_v1 `
  --out results\flood_pytorchsim_backend_v1\hpca_table_summary_v1\README.md

& $Python flood_local\build_numerical_quality_microbench.py `
  --out-dir results\flood_pytorchsim_backend_v1\numerical_quality_microbench_v1

& $Python flood_local\build_hpca_experiment_tables.py `
  --gate-dir results\flood_pytorchsim_backend_v1\hpca_submission_gate_v1 `
  --workload-details results\flood_pytorchsim_backend_v1\group16_v7_workload_v1\group16_v7_workload_details.csv `
  --quality-microbench results\flood_pytorchsim_backend_v1\numerical_quality_microbench_v1\quant_outlier_softmax_quality.csv `
  --out-dir $OutDir

Write-Host "HPCA paper data pipeline complete. Tables written to $OutDir"
