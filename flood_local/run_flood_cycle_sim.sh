#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python3}"
OUT_DIR="${OUT_DIR:-results/flood_cycle_sim_v1}"

run() {
  echo "[run] $*"
  "$@"
}

find_person2() {
  find . \
    -path './.git' -prune -o \
    -path './_gitdir' -prune -o \
    -path './tmp' -prune -o \
    -path './FLOOD' -prune -o \
    -path './PyTorchSim' -prune -o \
    -type f -name person2_pytorchsim_transformer.csv -print 2>/dev/null | head -n 1
}

mkdir -p "$OUT_DIR"
{
  echo "key,value"
  echo "runner,run_flood_cycle_sim.sh"
  echo "cwd,$(pwd)"
  echo "python,$($PYTHON --version 2>&1)"
  echo "git_commit,$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "out_dir,$OUT_DIR"
} > "$OUT_DIR/linux_runner_environment.csv"

SOURCE_BUNDLE_MANIFEST="$OUT_DIR/source_bundle/rtl_source_bundle_manifest.csv"
if [[ -f "$SOURCE_BUNDLE_MANIFEST" ]]; then
  run "$PYTHON" flood_local/build_rtl_source_bundle.py \
    --verify-root . \
    --manifest "$SOURCE_BUNDLE_MANIFEST" \
    --out-dir "$OUT_DIR/source_bundle_auto_verify"
else
  mkdir -p "$OUT_DIR/source_bundle_auto_verify"
  {
    echo "verify_status,checked_files,failed_files,expected_bundle_signature_sha256,actual_bundle_signature_sha256,policy"
    echo "skipped,0,0,,,No source bundle manifest found; full local source tree is assumed for this run."
  } > "$OUT_DIR/source_bundle_auto_verify/rtl_source_bundle_verify_summary.csv"
fi

run "$PYTHON" flood_local/build_mechanism_inventory.py \
  --base-root FLOOD \
  --out-dir "$OUT_DIR/mechanism_inventory"

run "$PYTHON" flood_local/build_rtl_source_manifest.py \
  --base-root FLOOD \
  --out-dir "$OUT_DIR/rtl_source_manifest"

run "$PYTHON" flood_local/build_mactree_profile.py \
  --base-root FLOOD \
  --mactree-root mactree/flood \
  --out-dir "$OUT_DIR/mactree_profile"

run "$PYTHON" flood_local/build_sparsity_profiles.py \
  --base-root FLOOD \
  --mechanism zero_skip zero-skip/flood \
  --mechanism channel_group_sparsity "channel group sparisy/flood" \
  --out-dir "$OUT_DIR/sparsity_profiles"

run "$PYTHON" flood_local/build_quant_outlier_profiles.py \
  --base-root FLOOD \
  --mechanism int8_int4 INT8-INT4/flood \
  --mechanism outlier outlier/flood \
  --out-dir "$OUT_DIR/quant_outlier_profiles"

run "$PYTHON" flood_local/flood_cycle_sim.py \
  --out-dir "$OUT_DIR/rtl_validation" \
  --rtl-validation results/flood_pytorchsim_backend_v1/workload_direct_rtl_validation_v1/workload_direct_validation_details.csv

WORKLOAD_DIRS=()
PERSON2_CSV="$(find_person2 || true)"
if [[ -n "$PERSON2_CSV" ]]; then
  run "$PYTHON" flood_local/flood_cycle_sim.py \
    --input "$PERSON2_CSV" \
    --out-dir "$OUT_DIR/person2_gemm" \
    --cycle-trace-cap 2000 \
    --include-system \
    --emit-paper-tables
  WORKLOAD_DIRS+=("person2_gemm")
else
  mkdir -p "$OUT_DIR/person2_gemm"
  {
    echo "input,status,policy"
    echo "person2_pytorchsim_transformer.csv,missing,No synthetic replacement is generated; missing evidence must remain blocked."
  } > "$OUT_DIR/person2_gemm/missing_input_report.csv"
fi

run "$PYTHON" flood_local/flood_cycle_sim.py \
  --input results/synthetic_unet_trace_v1/synthetic_unet_workload_from_trace_v1.csv \
  --out-dir "$OUT_DIR/synthetic_unet_trace" \
  --include-system \
  --emit-paper-tables
WORKLOAD_DIRS+=("synthetic_unet_trace")

run "$PYTHON" flood_local/flood_cycle_sim.py \
  --input "$OUT_DIR/softmax_smoke/softmax_workload.csv" \
  --out-dir "$OUT_DIR/softmax_smoke" \
  --cycle-trace-cap 500 \
  --emit-paper-tables
WORKLOAD_DIRS+=("softmax_smoke")

run "$PYTHON" flood_local/flood_cycle_sim.py \
  --out-dir "$OUT_DIR/system_calibration_smoke" \
  --system-calibration "$OUT_DIR/system_calibration_smoke/system_calibration_input.csv" \
  --system-model "$OUT_DIR/system_calibration_smoke/system_model_input.csv"

run "$PYTHON" flood_local/parse_system_calibration_logs.py \
  --template "$OUT_DIR/system_log_parse_smoke/template.csv" \
  --log-map "$OUT_DIR/system_log_parse_smoke/log_map.csv" \
  --out "$OUT_DIR/system_log_parse_smoke/parsed_system_calibration.csv"

run "$PYTHON" flood_local/flood_cycle_sim.py \
  --out-dir "$OUT_DIR/system_log_parse_smoke" \
  --system-calibration "$OUT_DIR/system_log_parse_smoke/parsed_system_calibration.csv"

run "$PYTHON" flood_local/flood_cycle_sim.py \
  --out-dir "$OUT_DIR/value_checker_smoke/pass_case" \
  --value-check-only \
  --golden-values "$OUT_DIR/value_checker_smoke/golden_values.txt" \
  --rtl-values "$OUT_DIR/value_checker_smoke/rtl_values_pass.txt"

run "$PYTHON" flood_local/flood_cycle_sim.py \
  --out-dir "$OUT_DIR/value_checker_smoke/fail_case" \
  --value-check-only \
  --golden-values "$OUT_DIR/value_checker_smoke/golden_values.txt" \
  --rtl-values "$OUT_DIR/value_checker_smoke/rtl_values_fail.txt"

run "$PYTHON" flood_local/run_value_check_batch.py \
  --manifest "$OUT_DIR/value_check_batch_templates/value_check_smoke_manifest.csv" \
  --out-root "$OUT_DIR/value_check_batch_smoke"

run "$PYTHON" flood_local/run_paper_workload_batch.py \
  --manifest "$OUT_DIR/batch_templates/batch_smoke_manifest.csv" \
  --out-root "$OUT_DIR/batch_smoke"

run "$PYTHON" flood_local/run_system_calibration_batch.py \
  --manifest "$OUT_DIR/system_calibration_batch_templates/system_calibration_smoke_manifest.csv" \
  --out-root "$OUT_DIR/system_calibration_batch_smoke"

run "$PYTHON" flood_local/build_paper_data_gate.py \
  --manifest "$OUT_DIR/final_paper_gate_templates/final_paper_gate_smoke_manifest.csv" \
  --workload-gate "$OUT_DIR/batch_smoke/batch_readiness_summary.csv" \
  --value-gate "$OUT_DIR/value_check_batch_smoke/value_readiness_summary.csv" \
  --system-gate "$OUT_DIR/system_calibration_batch_smoke/calibration_readiness_summary.csv" \
  --rtl-source-summary "$OUT_DIR/rtl_source_manifest/rtl_source_summary.csv" \
  --out-dir "$OUT_DIR/final_paper_gate_smoke"

run "$PYTHON" flood_local/export_main_figure_package.py \
  --final-gate "$OUT_DIR/final_paper_gate_smoke/final_paper_data_gate.csv" \
  --out-dir "$OUT_DIR/main_figure_export_smoke"

run "$PYTHON" flood_local/audit_main_figure_export.py \
  --final-gate "$OUT_DIR/final_paper_gate_smoke/final_paper_data_gate.csv" \
  --export-dir "$OUT_DIR/main_figure_export_smoke" \
  --out-dir "$OUT_DIR/main_figure_export_audit_smoke"

TIMELINE_ARGS=()
for dir_name in "${WORKLOAD_DIRS[@]}"; do
  TIMELINE_ARGS+=("$OUT_DIR/$dir_name")
done
run "$PYTHON" flood_local/build_timeline_consistency_report.py \
  --out-dir "$OUT_DIR/timeline_consistency" \
  "${TIMELINE_ARGS[@]}"

COVERAGE_ARGS=()
for dir_name in "${WORKLOAD_DIRS[@]}"; do
  COVERAGE_ARGS+=(--workload-dir "$dir_name")
done
run "$PYTHON" flood_local/build_validation_coverage_matrix.py \
  --results-root "$OUT_DIR" \
  --out-dir "$OUT_DIR/validation_coverage" \
  "${COVERAGE_ARGS[@]}"

run "$PYTHON" flood_local/build_rtl_task_manifest.py \
  --priority-csv "$OUT_DIR/validation_coverage/next_rtl_validation_priority.csv" \
  --out-dir "$OUT_DIR/rtl_task_manifest" \
  --limit 20

run "$PYTHON" flood_local/check_rtl_task_manifest.py \
  --task-csv "$OUT_DIR/rtl_task_manifest/rtl_validation_tasks.csv" \
  --system-manifest "$OUT_DIR/rtl_task_manifest/system_calibration_manifest_draft.csv" \
  --value-manifest "$OUT_DIR/rtl_task_manifest/value_check_manifest_draft.csv" \
  --out-dir "$OUT_DIR/rtl_task_manifest_check"

run "$PYTHON" flood_local/run_completed_rtl_task_ingest.py \
  --task-csv "$OUT_DIR/completed_ingest_smoke_inputs/task_manifest.csv" \
  --system-manifest "$OUT_DIR/completed_ingest_smoke_inputs/system_manifest.csv" \
  --value-manifest "$OUT_DIR/completed_ingest_smoke_inputs/value_manifest.csv" \
  --paper-gate-manifest "$OUT_DIR/completed_ingest_smoke_inputs/paper_gate_manifest.csv" \
  --workload-gate "$OUT_DIR/batch_smoke/batch_readiness_summary.csv" \
  --rtl-source-summary "$OUT_DIR/rtl_source_manifest/rtl_source_summary.csv" \
  --out-root "$OUT_DIR/completed_ingest_smoke"

run "$PYTHON" flood_local/audit_main_figure_export.py \
  --final-gate "$OUT_DIR/completed_ingest_smoke/final_gate/final_paper_data_gate.csv" \
  --export-dir "$OUT_DIR/completed_ingest_smoke/main_figure_export" \
  --out-dir "$OUT_DIR/completed_ingest_smoke/main_figure_export_audit"

run "$PYTHON" flood_local/build_hpca_figure_contract.py \
  --results-root "$OUT_DIR" \
  --legacy-micro-dir results/flood_pytorchsim_backend_v1/legacy_micro_data_v1 \
  --backend-root results/flood_pytorchsim_backend_v1 \
  --out-dir "$OUT_DIR/hpca_figure_contract"

run "$PYTHON" flood_local/ingest_real_workload_rtl_subset.py \
  --input "$OUT_DIR/server_rtl_real_workload_v1/real_workload_rtl_subset_v1.csv" \
  --out-dir "$OUT_DIR/real_workload_rtl_subset_ingest"

run "$PYTHON" flood_local/build_real_workload_rtl_expansion_plan.py \
  --gate-csv "$OUT_DIR/real_workload_rtl_subset_ingest/real_workload_rtl_subset_gate.csv" \
  --out-dir "$OUT_DIR/real_workload_rtl_expansion_plan"

run "$PYTHON" flood_local/ingest_rtl_expansion_results.py \
  --raw-csv "$OUT_DIR/server_rtl_real_workload_v2/p0_expansion_results.csv" \
  --log-root "$OUT_DIR/server_rtl_real_workload_v2/logs" \
  --out-dir "$OUT_DIR/rtl_expansion_results_ingest"

run "$PYTHON" flood_local/build_rtl_tile_projection.py \
  --expansion-gate "$OUT_DIR/rtl_expansion_results_ingest/rtl_expansion_results_gate.csv" \
  --expansion-plan "$OUT_DIR/real_workload_rtl_expansion_plan/next_server_run_manifest.csv" \
  --out-dir "$OUT_DIR/rtl_tile_projection"

run "$PYTHON" flood_local/prepare_rtl_repeat_value_checks.py \
  --server-root "$OUT_DIR/server_rtl_value_repeat_v1" \
  --out-dir "$OUT_DIR/rtl_value_repeat_prepare"

run "$PYTHON" flood_local/run_value_check_batch.py \
  --manifest "$OUT_DIR/rtl_value_repeat_prepare/value_repeat_manifest.csv" \
  --out-root "$OUT_DIR/rtl_value_repeat_check"

run "$PYTHON" flood_local/build_rtl_value_repeat_gate.py \
  --prepare-summary "$OUT_DIR/rtl_value_repeat_prepare/value_repeat_prepare_summary.csv" \
  --value-summary "$OUT_DIR/rtl_value_repeat_check/merged_value_check_summary.csv" \
  --out-dir "$OUT_DIR/rtl_value_repeat_gate"

run "$PYTHON" flood_local/build_postprocessor_scorecard.py \
  --results-root "$OUT_DIR" \
  --out-dir "$OUT_DIR/postprocessor_scorecard"

run "$PYTHON" flood_local/build_simulator_readiness_report.py \
  --results-root "$OUT_DIR" \
  --out-dir "$OUT_DIR/readiness_report"

echo "FLOOD cycle simulator Linux regression finished: $OUT_DIR"
