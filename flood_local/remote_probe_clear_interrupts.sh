#!/usr/bin/env bash
set -u
cd /root/autodl-tmp/torchsim_work/flood_rtl_calibration

run_probe() {
  name=$1; k=$2; cout=$3; gs=$4; cin=$5; rc_total=$6; rr_total=$7; limit=$8
  gn=$((16/gs))
  log=logs/${name}.log
  python3 make_simple_hex.py --k "$k" --cout "$cout" --group-size "$gs" --group-num "$gn" --cin-idx-total "$cin" --res-cols "$rc_total" --res-rows "$rr_total" > "logs/${name}.hexgen.log" 2>&1
  timeout "$limit" vvp run/calib_01_zeroinit_fixed_clean.vvp +K="$k" +COUT="$cout" +GROUP_SIZE="$gs" +CIN_IDX_TOTAL="$cin" +RES_COLS="$rc_total" +RES_ROWS="$rr_total" > "$log" 2>&1
  rc=$?
  cycles=$(grep -o 'Done interrupt after [0-9]* cycles' "$log" | awk '{print $4}' | paste -sd ';' -)
  if [ -z "$cycles" ]; then cycles=NA; fi
  echo "$name rc=$rc cycles=$cycles"
  grep -n -E 'Interrupts cleared|WARN|Special config|Trigger run|Done interrupt|xxxxxxxx' "$log" | head -n 120
}

run_probe u06_k1_c12_g16_rc2_clear 1 12 16 1 2 1 1500
run_probe b07_k1_c6_g16_ci2_clear 1 6 16 2 1 1 1200
run_probe b08_k1_c6_g16_ci3_clear 1 6 16 3 1 1 1500
