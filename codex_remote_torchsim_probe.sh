#!/usr/bin/env bash
set -euo pipefail

for spec in \
  "PSAL-POSTECH/llvm-project v1.0.8" \
  "PSAL-POSTECH/riscv-isa-sim v1.0.1" \
  "PSAL-POSTECH/gem5 v1.0.1"
do
  repo="${spec% *}"
  tag="${spec#* }"
  echo "== ${repo} ${tag} =="
  curl -fsSL "https://api.github.com/repos/${repo}/releases/tags/${tag}" |
    jq -r '.assets[] | [.name, .size, .browser_download_url] | @tsv'
done

echo "== tools =="
export PATH=/root/miniconda3/bin:/root/.local/bin:/root/miniconda3/envs/conan156/bin:$PATH
for tool in python conan cmake ninja mlir-opt mlir-translate llc riscv64-unknown-elf-gcc spike pk; do
  printf '%-28s' "${tool}:"
  command -v "${tool}" || true
done
