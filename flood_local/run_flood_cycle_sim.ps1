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

& $Python flood_local\build_rtl_source_manifest.py `
    --base-root FLOOD `
    --out-dir "$OutDir\rtl_source_manifest"

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

& $Python flood_local\run_value_check_batch.py `
    --manifest "$OutDir\value_check_batch_templates\value_check_smoke_manifest.csv" `
    --out-root "$OutDir\value_check_batch_smoke"

& $Python flood_local\run_paper_workload_batch.py `
    --manifest "$OutDir\batch_templates\batch_smoke_manifest.csv" `
    --out-root "$OutDir\batch_smoke"

& $Python flood_local\run_system_calibration_batch.py `
    --manifest "$OutDir\system_calibration_batch_templates\system_calibration_smoke_manifest.csv" `
    --out-root "$OutDir\system_calibration_batch_smoke"

& $Python flood_local\build_paper_data_gate.py `
    --manifest "$OutDir\final_paper_gate_templates\final_paper_gate_smoke_manifest.csv" `
    --workload-gate "$OutDir\batch_smoke\batch_readiness_summary.csv" `
    --value-gate "$OutDir\value_check_batch_smoke\value_readiness_summary.csv" `
    --system-gate "$OutDir\system_calibration_batch_smoke\calibration_readiness_summary.csv" `
    --rtl-source-summary "$OutDir\rtl_source_manifest\rtl_source_summary.csv" `
    --out-dir "$OutDir\final_paper_gate_smoke"

& $Python flood_local\export_main_figure_package.py `
    --final-gate "$OutDir\final_paper_gate_smoke\final_paper_data_gate.csv" `
    --out-dir "$OutDir\main_figure_export_smoke"

& $Python flood_local\audit_main_figure_export.py `
    --final-gate "$OutDir\final_paper_gate_smoke\final_paper_data_gate.csv" `
    --export-dir "$OutDir\main_figure_export_smoke" `
    --out-dir "$OutDir\main_figure_export_audit_smoke"

& $Python flood_local\build_timeline_consistency_report.py `
    --out-dir "$OutDir\timeline_consistency" `
    "$OutDir\person2_gemm" `
    "$OutDir\synthetic_unet_trace" `
    "$OutDir\softmax_smoke"

& $Python flood_local\build_validation_coverage_matrix.py `
    --results-root "$OutDir" `
    --out-dir "$OutDir\validation_coverage" `
    --workload-dir person2_gemm `
    --workload-dir synthetic_unet_trace `
    --workload-dir softmax_smoke

& $Python flood_local\build_rtl_task_manifest.py `
    --priority-csv "$OutDir\validation_coverage\next_rtl_validation_priority.csv" `
    --out-dir "$OutDir\rtl_task_manifest" `
    --limit 20

& $Python flood_local\check_rtl_task_manifest.py `
    --task-csv "$OutDir\rtl_task_manifest\rtl_validation_tasks.csv" `
    --system-manifest "$OutDir\rtl_task_manifest\system_calibration_manifest_draft.csv" `
    --value-manifest "$OutDir\rtl_task_manifest\value_check_manifest_draft.csv" `
    --out-dir "$OutDir\rtl_task_manifest_check"

& $Python flood_local\run_completed_rtl_task_ingest.py `
    --task-csv "$OutDir\completed_ingest_smoke_inputs\task_manifest.csv" `
    --system-manifest "$OutDir\completed_ingest_smoke_inputs\system_manifest.csv" `
    --value-manifest "$OutDir\completed_ingest_smoke_inputs\value_manifest.csv" `
    --paper-gate-manifest "$OutDir\completed_ingest_smoke_inputs\paper_gate_manifest.csv" `
    --workload-gate "$OutDir\batch_smoke\batch_readiness_summary.csv" `
    --rtl-source-summary "$OutDir\rtl_source_manifest\rtl_source_summary.csv" `
    --out-root "$OutDir\completed_ingest_smoke"

& $Python flood_local\audit_main_figure_export.py `
    --final-gate "$OutDir\completed_ingest_smoke\final_gate\final_paper_data_gate.csv" `
    --export-dir "$OutDir\completed_ingest_smoke\main_figure_export" `
    --out-dir "$OutDir\completed_ingest_smoke\main_figure_export_audit"

& $Python flood_local\build_hpca_figure_contract.py `
    --results-root "$OutDir" `
    --legacy-micro-dir results\flood_pytorchsim_backend_v1\legacy_micro_data_v1 `
    --backend-root results\flood_pytorchsim_backend_v1 `
    --out-dir "$OutDir\hpca_figure_contract"

& $Python flood_local\ingest_real_workload_rtl_subset.py `
    --input "$OutDir\server_rtl_real_workload_v1\real_workload_rtl_subset_v1.csv" `
    --out-dir "$OutDir\real_workload_rtl_subset_ingest"

& $Python flood_local\build_real_workload_rtl_expansion_plan.py `
    --gate-csv "$OutDir\real_workload_rtl_subset_ingest\real_workload_rtl_subset_gate.csv" `
    --out-dir "$OutDir\real_workload_rtl_expansion_plan"

& $Python flood_local\ingest_rtl_expansion_results.py `
    --raw-csv "$OutDir\server_rtl_real_workload_v2\p0_expansion_results.csv" `
    --log-root "$OutDir\server_rtl_real_workload_v2\logs" `
    --out-dir "$OutDir\rtl_expansion_results_ingest"

& $Python flood_local\build_rtl_tile_projection.py `
    --expansion-gate "$OutDir\rtl_expansion_results_ingest\rtl_expansion_results_gate.csv" `
    --expansion-plan "$OutDir\real_workload_rtl_expansion_plan\next_server_run_manifest.csv" `
    --out-dir "$OutDir\rtl_tile_projection"

& $Python flood_local\prepare_rtl_repeat_value_checks.py `
    --server-root "$OutDir\server_rtl_value_repeat_v1" `
    --out-dir "$OutDir\rtl_value_repeat_prepare"

& $Python flood_local\run_value_check_batch.py `
    --manifest "$OutDir\rtl_value_repeat_prepare\value_repeat_manifest.csv" `
    --out-root "$OutDir\rtl_value_repeat_check"

& $Python flood_local\build_rtl_value_repeat_gate.py `
    --prepare-summary "$OutDir\rtl_value_repeat_prepare\value_repeat_prepare_summary.csv" `
    --value-summary "$OutDir\rtl_value_repeat_check\merged_value_check_summary.csv" `
    --out-dir "$OutDir\rtl_value_repeat_gate"

& $Python flood_local\build_postprocessor_scorecard.py `
    --results-root "$OutDir" `
    --out-dir "$OutDir\postprocessor_scorecard"

& $Python flood_local\build_simulator_readiness_report.py `
    --results-root "$OutDir" `
    --out-dir "$OutDir\readiness_report"

Write-Host "FLOOD cycle simulator regression finished: $OutDir"
