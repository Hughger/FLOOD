#!/usr/bin/env bash
set -u
cd /root/autodl-tmp/torchsim_work/flood_rtl_calibration

out=results/rtl_fixed_clean_validation_zeroinit.csv
echo case,k,cout,group_size,group_num,cin_idx_total,res_cols,res_rows,rc,run_count,cycle_list,total_cycles,x_count,log > "$out"

run_case() {
  name=$1; k=$2; cout=$3; gs=$4; cin=$5; rc_total=$6; rr_total=$7; limit=$8
  gn=$((16/gs))
  log=logs/${name}.log
  python3 make_simple_hex.py --k "$k" --cout "$cout" --group-size "$gs" --group-num "$gn" --cin-idx-total "$cin" --res-cols "$rc_total" --res-rows "$rr_total" > "logs/${name}.hexgen.log" 2>&1
  timeout "$limit" vvp run/calib_01_zeroinit_fixed_clean.vvp +K="$k" +COUT="$cout" +GROUP_SIZE="$gs" +CIN_IDX_TOTAL="$cin" +RES_COLS="$rc_total" +RES_ROWS="$rr_total" > "$log" 2>&1
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
  x_count=$(grep -c 'xxxxxxxx' "$log" || true)
  echo "$name,$k,$cout,$gs,$gn,$cin,$rc_total,$rr_total,$rc,$count,$cycles,$total,$x_count,$log" >> "$out"
}

run_case f01_k1_c6_g16_ci2_fixed 1 6 16 2 1 1 1200
run_case f02_k1_c6_g16_ci3_fixed 1 6 16 3 1 1 1500
run_case f03_k1_c6_g16_ci4_fixed 1 6 16 4 1 1 1800
run_case f04_k1_c12_g16_rc2_fixed 1 12 16 1 2 1 1500
