#!/usr/bin/env bash
set -u
cd /root/autodl-tmp/torchsim_work/flood_rtl_calibration

out=results/rtl_v4_independent_validation_zeroinit.csv
status=logs/run_v4_independent_validation.status
: > "$status"
echo case,k,cout,group_size,group_num,cin_idx_total,res_cols,res_rows,rc,run_count,cycle_list,total_cycles,log > "$out"

run_case() {
  name=$1; k=$2; cout=$3; gs=$4; cin=$5; rc_total=$6; rr_total=$7; limit=$8
  gn=$((16/gs))
  log=logs/${name}.log
  echo [START] "$name" k="$k" cout="$cout" gs="$gs" cin="$cin" rc="$rc_total" rr="$rr_total" "$(date)" | tee -a "$status"
  python3 make_simple_hex.py --k "$k" --cout "$cout" --group-size "$gs" --group-num "$gn" --cin-idx-total "$cin" --res-cols "$rc_total" --res-rows "$rr_total" > "logs/${name}.hexgen.log" 2>&1
  timeout "$limit" vvp run/calib_01_zeroinit.vvp +K="$k" +COUT="$cout" +GROUP_SIZE="$gs" +CIN_IDX_TOTAL="$cin" +RES_COLS="$rc_total" +RES_ROWS="$rr_total" > "$log" 2>&1
  rc=$?
  cycles=$(grep -o 'Done interrupt after [0-9]* cycles' "$log" | awk '{print $4}' | paste -sd ';' -)
  if [ -z "$cycles" ]; then
    cycles=NA
    count=0
    total=NA
  else
    count=$(printf '%s' "$cycles" | awk -F';' '{print NF}')
    total=$(printf '%s' "$cycles" | awk -F';' '{s=0; for(i=1;i<=NF;i++) s+=$i; print s}')
  fi
  echo "$name,$k,$cout,$gs,$gn,$cin,$rc_total,$rr_total,$rc,$count,$cycles,$total,$log" >> "$out"
  echo [DONE] "$name" rc="$rc" runs="$count" total="$total" cycles="$cycles" "$(date)" | tee -a "$status"
}

run_case u01_k3_c6_g8_ci1 3 6 8 1 1 1 1200
run_case u02_k3_c12_g8_ci1 3 12 8 1 1 1 1500
run_case u03_k3_c6_g8_ci2 3 6 8 2 1 1 1500
run_case u04_k1_c10_g16_ci1 1 10 16 1 1 1 1200
run_case u05_k1_c16_g16_ci1 1 16 16 1 1 1 1500
run_case u06_k1_c12_g16_rc2 1 12 16 1 2 1 1500
