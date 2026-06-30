#!/usr/bin/env bash
set -euo pipefail

export PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/root/.local/bin:/root/miniconda3/envs/conan156/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:/root/miniconda3/lib:${LD_LIBRARY_PATH:-}
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6

repo=/root/autodl-tmp/torchsim_work/PyTorchSim
cd "${repo}"
export TORCHSIM_DIR="${repo}"
export PYTHONPATH="${repo}:${PYTHONPATH:-}"
export TOGSIM_CONFIG="${repo}/configs/systolic_ws_128x128_c1_simple_noc_tpuv3_timing_only.yml"
export TORCHSIM_LOG_PATH=/root/autodl-tmp/torchsim_work/results/raw_logs
mkdir -p "${TORCHSIM_LOG_PATH}"

echo "== import check =="
python - <<'PY'
import torch
import torch_openreg
print("torch", torch.__version__)
print("has_npu", hasattr(torch, "npu"))
print("device", torch.device("npu:0"))
PY

echo "== tool check =="
for tool in mlir-opt mlir-translate llc riscv64-unknown-elf-gcc spike pk; do
  printf '%-28s' "${tool}:"
  command -v "${tool}" || true
done

echo "== smoke gemm =="
python experiments/gemm.py --size 128 128 128
