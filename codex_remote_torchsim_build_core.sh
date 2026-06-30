#!/usr/bin/env bash
set -euo pipefail

export PATH=/root/miniconda3/bin:/root/.local/bin:/root/miniconda3/envs/conan156/bin:$PATH
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/root/miniconda3/lib:${LD_LIBRARY_PATH:-}

base=/root/autodl-tmp/torchsim_work
repo="${base}/PyTorchSim"

cd "${repo}"
git checkout 509f42554202edb29cf8d31ddf619776f465e717
git submodule update --init --recursive

echo "== build TOGSim =="
cd "${repo}/TOGSim"
mkdir -p build
cd build
if [ ! -f "${HOME}/.conan/profiles/default" ]; then
  conan profile new default --detect
fi
conan profile update settings.compiler.libcxx=libstdc++ default
conan install .. --build=missing
cmake ..
make -j"$(nproc)"

echo "== install PyTorchSimDevice =="
cd "${repo}/PyTorchSimDevice"
python -m pip install --no-build-isolation -e .

echo "== import check =="
cd "${repo}"
export TORCHSIM_DIR="${repo}"
export PYTHONPATH="${repo}:${PYTHONPATH:-}"
python -c "import torch; import torch_openreg; print('torch', torch.__version__); print('npu?', hasattr(torch, 'npu')); print(torch.device('npu:0'))"
