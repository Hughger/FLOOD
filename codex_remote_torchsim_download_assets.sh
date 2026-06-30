#!/usr/bin/env bash
set -euo pipefail

base=/root/autodl-tmp/torchsim_work
dl="${base}/downloads"
mkdir -p "${dl}"

download_one() {
  local name="$1"
  local url="$2"
  local out="${dl}/${name}"
  echo "== download ${name} =="
  if [ -s "${out}" ]; then
    echo "partial/current: $(du -h "${out}" | awk '{print $1}')"
  fi
  curl -L --fail --retry 20 --retry-delay 5 --connect-timeout 30 \
    --speed-time 120 --speed-limit 1024 \
    -C - -o "${out}" "${url}"
  ls -lh "${out}"
}

download_one "riscv-llvm-release.tar.gz" \
  "https://github.com/PSAL-POSTECH/llvm-project/releases/download/v1.0.8/riscv-llvm-release.tar.gz"

download_one "spike-release.tar.gz" \
  "https://github.com/PSAL-POSTECH/riscv-isa-sim/releases/download/v1.0.1/spike-release.tar.gz"

download_one "gem5-release.tar.gz" \
  "https://github.com/PSAL-POSTECH/gem5/releases/download/v1.0.1/gem5-release.tar.gz"

download_one "riscv64-elf-ubuntu-20.04-llvm-nightly-2023.12.14-nightly.tar.gz" \
  "https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/2023.12.14/riscv64-elf-ubuntu-20.04-llvm-nightly-2023.12.14-nightly.tar.gz"

echo "== extract =="
mkdir -p "${base}/gem5" "${base}/riscv"
if [ ! -x "${base}/gem5/release/gem5.opt" ]; then
  tar -xzf "${dl}/gem5-release.tar.gz" -C "${base}/gem5"
fi
if [ ! -x "${base}/riscv-llvm/bin/mlir-opt" ]; then
  tar -xzf "${dl}/riscv-llvm-release.tar.gz" -C "${base}"
fi
if [ ! -x "${base}/release/bin/spike" ]; then
  tar -xzf "${dl}/spike-release.tar.gz" -C "${base}"
fi
if [ ! -x "${base}/riscv/bin/riscv64-unknown-elf-gcc" ]; then
  tar -xzf "${dl}/riscv64-elf-ubuntu-20.04-llvm-nightly-2023.12.14-nightly.tar.gz" -C "${base}/riscv" --strip-components=1
fi

echo "== tools =="
ls -l \
  "${base}/riscv-llvm/bin/mlir-opt" \
  "${base}/release/bin/spike" \
  "${base}/gem5/release/gem5.opt" \
  "${base}/riscv/bin/riscv64-unknown-elf-gcc"
