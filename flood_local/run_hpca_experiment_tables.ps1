param(
  [string]$OutDir = "results\flood_pytorchsim_backend_v1\hpca_experiment_tables_v1"
)

$ErrorActionPreference = "Stop"
$Python = "C:\Users\98676\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $Python)) {
  $Python = "python"
}

& $Python flood_local\build_hpca_experiment_tables.py `
  --gate-dir results\flood_pytorchsim_backend_v1\hpca_submission_gate_v1 `
  --workload-details results\flood_pytorchsim_backend_v1\group16_v7_workload_v1\group16_v7_workload_details.csv `
  --out-dir $OutDir

Write-Host "HPCA experiment tables written to $OutDir"
