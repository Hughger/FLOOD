#!/usr/bin/env bash
set -euo pipefail

echo "TIME=$(date '+%F %T')"
echo "== running build-related processes =="
ps -ef |
  grep -E 'build_core|cmake|make|conan|cc1plus|g\+\+|c\+\+|Simulator' |
  grep -v grep || true

echo "== build artifacts =="
if [ -x /root/autodl-tmp/torchsim_work/PyTorchSim/TOGSim/build/bin/Simulator ]; then
  echo "TOGSIM_BUILT"
else
  echo "TOGSIM_NOT_BUILT"
fi

if [ -d /root/autodl-tmp/torchsim_work/PyTorchSim/TOGSim/build ]; then
  find /root/autodl-tmp/torchsim_work/PyTorchSim/TOGSim/build -maxdepth 3 \
    \( -name Simulator -o -name '*.so' -o -name CMakeCache.txt \) |
    sort |
    head -50
fi

echo "== disk =="
df -h / /root/autodl-tmp
