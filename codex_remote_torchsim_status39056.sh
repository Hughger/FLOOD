#!/usr/bin/env bash
set -euo pipefail

base=/root/autodl-tmp/torchsim_work
repo="${base}/PyTorchSim"

echo "TIME=$(date '+%F %T')"
echo "== processes =="
ps -ef |
  grep -E 'download_assets|curl|aria2c|tar|cmake|make|conan|cc1plus|g\+\+|c\+\+|Simulator' |
  grep -v grep || true

echo "== artifacts =="
test -x "${repo}/TOGSim/build/bin/Simulator" && echo "TOGSIM_BUILT=yes" || echo "TOGSIM_BUILT=no"
test -x "${base}/riscv-llvm/bin/mlir-opt" && echo "MLIR_READY=yes" || echo "MLIR_READY=no"
test -x "${base}/release/bin/spike" && echo "SPIKE_READY=yes" || echo "SPIKE_READY=no"
test -x "${base}/gem5/release/gem5.opt" && echo "GEM5_READY=yes" || echo "GEM5_READY=no"
test -x "${base}/riscv/bin/riscv64-unknown-elf-gcc" && echo "RISCV_GCC_READY=yes" || echo "RISCV_GCC_READY=no"

echo "== downloads =="
ls -lh "${base}/downloads" 2>/dev/null || true

echo "== log tail =="
tail -n 25 "${base}/download_assets.log" 2>/dev/null || true
