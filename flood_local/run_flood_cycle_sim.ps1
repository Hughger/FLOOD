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

& $Python flood_local\build_mechanism_inventory.py `
    --base-root FLOOD `
    --out-dir "$OutDir\mechanism_inventory"

& $Python flood_local\build_mactree_profile.py `
    --base-root FLOOD `
    --mactree-root mactree\flood `
    --out-dir "$OutDir\mactree_profile"

& $Python flood_local\build_sparsity_profiles.py `
    --base-root FLOOD `
    --mechanism zero_skip zero-skip\flood `
    --mechanism channel_group_sparsity "channel group sparisy\flood" `
    --out-dir "$OutDir\sparsity_profiles"

& $Python flood_local\build_quant_outlier_profiles.py `
    --base-root FLOOD `
    --mechanism int8_int4 INT8-INT4\flood `
    --mechanism outlier outlier\flood `
    --out-dir "$OutDir\quant_outlier_profiles"

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
    --input "$OutDir\softmax_smoke\softmax_workload.csv" `
    --out-dir "$OutDir\softmax_smoke" `
    --cycle-trace-cap 500 `
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

& $Python flood_local\run_paper_workload_batch.py `
    --manifest "$OutDir\batch_templates\batch_smoke_manifest.csv" `
    --out-root "$OutDir\batch_smoke"

& $Python flood_local\build_simulator_readiness_report.py `
    --results-root "$OutDir" `
    --out-dir "$OutDir\readiness_report"

Write-Host "FLOOD cycle simulator regression finished: $OutDir"
