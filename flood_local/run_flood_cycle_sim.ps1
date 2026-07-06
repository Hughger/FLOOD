param(
    [string]$Python = "C:\Users\98676\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    [string]$OutDir = "results\flood_cycle_sim_v1"
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

$searchRoots = Get-ChildItem -Path . -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notin @("FLOOD", "PyTorchSim", ".git", "_gitdir", "tmp") }
$person2 = $searchRoots |
    ForEach-Object { Get-ChildItem -Path $_.FullName -Recurse -Filter person2_pytorchsim_transformer.csv -ErrorAction SilentlyContinue } |
    Select-Object -First 1
if (-not $person2) {
    throw "Cannot find person2_pytorchsim_transformer.csv under current workspace."
}

& $Python flood_local\flood_cycle_sim.py `
    --out-dir "$OutDir\rtl_validation" `
    --rtl-validation results\flood_pytorchsim_backend_v1\workload_direct_rtl_validation_v1\workload_direct_validation_details.csv

& $Python flood_local\flood_cycle_sim.py `
    --input $person2.FullName `
    --out-dir "$OutDir\person2_gemm" `
    --cycle-trace-cap 2000 `
    --include-system `
    --emit-paper-tables

& $Python flood_local\flood_cycle_sim.py `
    --input results\synthetic_unet_trace_v1\synthetic_unet_workload_from_trace_v1.csv `
    --out-dir "$OutDir\synthetic_unet_trace" `
    --include-system `
    --emit-paper-tables

& $Python flood_local\flood_cycle_sim.py `
    --out-dir "$OutDir\system_calibration_smoke" `
    --system-calibration "$OutDir\system_calibration_smoke\system_calibration_input.csv" `
    --system-model "$OutDir\system_calibration_smoke\system_model_input.csv"

& $Python flood_local\parse_system_calibration_logs.py `
    --template "$OutDir\system_log_parse_smoke\template.csv" `
    --log-map "$OutDir\system_log_parse_smoke\log_map.csv" `
    --out "$OutDir\system_log_parse_smoke\parsed_system_calibration.csv"

& $Python flood_local\flood_cycle_sim.py `
    --out-dir "$OutDir\system_log_parse_smoke" `
    --system-calibration "$OutDir\system_log_parse_smoke\parsed_system_calibration.csv"

& $Python flood_local\flood_cycle_sim.py `
    --out-dir "$OutDir\value_checker_smoke\pass_case" `
    --value-check-only `
    --golden-values "$OutDir\value_checker_smoke\golden_values.txt" `
    --rtl-values "$OutDir\value_checker_smoke\rtl_values_pass.txt"

& $Python flood_local\flood_cycle_sim.py `
    --out-dir "$OutDir\value_checker_smoke\fail_case" `
    --value-check-only `
    --golden-values "$OutDir\value_checker_smoke\golden_values.txt" `
    --rtl-values "$OutDir\value_checker_smoke\rtl_values_fail.txt"

Write-Host "FLOOD cycle simulator regression finished: $OutDir"
