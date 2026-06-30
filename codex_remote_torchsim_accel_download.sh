#!/usr/bin/env bash
set -euo pipefail

base=/root/autodl-tmp/torchsim_work
dl="${base}/downloads"
mkdir -p "${dl}"

echo "== stop old downloaders =="
pkill -f '/root/autodl-tmp/torchsim_work/download_assets.sh' || true
pkill -f 'riscv-llvm-release.tar.gz' || true

echo "== install aria2 if needed =="
if ! command -v aria2c >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y aria2
fi

download_one() {
  local name="$1"
  local url="$2"
  local out="${dl}/${name}"
  echo "== aria2 download ${name} =="
  aria2c \
    --continue=true \
    --max-connection-per-server=8 \
    --split=8 \
    --min-split-size=1M \
    --retry-wait=5 \
    --max-tries=0 \
    --summary-interval=30 \
    --dir="${dl}" \
    --out="${name}" \
    "${url}"
  ls -lh "${out}"
}

# The LLVM partial was previously written by two curl processes at once; restart it cleanly.
rm -f "${dl}/riscv-llvm-release.tar.gz" "${dl}/riscv-llvm-release.tar.gz.aria2"

download_one "riscv-llvm-release.tar.gz" \
  "https://github.com/PSAL-POSTECH/llvm-project/releases/download/v1.0.8/riscv-llvm-release.tar.gz"

download_one "spike-release.tar.gz" \
  "https://github.com/PSAL-POSTECH/riscv-isa-sim/releases/download/v1.0.1/spike-release.tar.gz"

# The existing gem5 partial is also from a previous slow curl attempt; let aria2 resume only if valid.
download_one "gem5-release.tar.gz" \
  "https://github.com/PSAL-POSTECH/gem5/releases/download/v1.0.1/gem5-release.tar.gz"

download_one "riscv64-elf-ubuntu-20.04-llvm-nightly-2023.12.14-nightly.tar.gz" \
  "https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/2023.12.14/riscv64-elf-ubuntu-20.04-llvm-nightly-2023.12.14-nightly.tar.gz"

echo "== extract =="
mkdir -p "${base}/gem5" "${base}/riscv"
if [ ! -x "${base}/riscv-llvm/bin/mlir-opt" ]; then
  tar -xzf "${dl}/riscv-llvm-release.tar.gz" -C "${base}"
fi
if [ ! -x "${base}/release/bin/spike" ]; then
  tar -xzf "${dl}/spike-release.tar.gz" -C "${base}"
fi
if [ ! -x "${base}/gem5/release/gem5.opt" ]; then
  tar -xzf "${dl}/gem5-release.tar.gz" -C "${base}/gem5"
fi
if [ ! -x "${base}/riscv/bin/riscv64-unknown-elf-gcc" ]; then
  tar -xzf "${dl}/riscv64-elf-ubuntu-20.04-llvm-nightly-2023.12.14-nightly.tar.gz" -C "${base}/riscv" --strip-components=1
fi

echo "== ready tools =="
ls -l \
  "${base}/riscv-llvm/bin/mlir-opt" \
  "${base}/release/bin/spike" \
  "${base}/gem5/release/gem5.opt" \
  "${base}/riscv/bin/riscv64-unknown-elf-gcc"
