param(
  [ValidateSet("shell", "smoke", "diffusion", "collect")]
  [string]$Suite = "smoke",
  [string]$Image = "ghcr.io/psal-postech/torchsim-ci:v1.1.0",
  [string]$Config = "/workspace/PyTorchSim/configs/systolic_ws_128x128_c1_simple_noc_tpuv3_timing_only.yml"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Repo = Join-Path $Root "PyTorchSim"
$Results = Join-Path $Root "results"
$RawLogs = Join-Path $Results "raw_logs"

New-Item -ItemType Directory -Force -Path $Results, $RawLogs | Out-Null

if ($Suite -eq "collect") {
  $Python = "C:\Users\98676\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if (-not (Test-Path $Python)) {
    throw "Bundled Python runtime was not found: $Python"
  }
  & $Python (Join-Path $PSScriptRoot "summarize_togsim_logs.py") `
    --log-root $RawLogs `
    --out (Join-Path $Results "layer_results\cycles.csv")
  exit $LASTEXITCODE
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker is not available in PATH. Install/start Docker Desktop, then rerun this script."
}

$repoDocker = $Repo -replace "\\", "/"
$resultsDocker = $Results -replace "\\", "/"

$commonEnv = @(
  "-e", "TORCHSIM_DIR=/workspace/PyTorchSim",
  "-e", "TOGSIM_CONFIG=$Config",
  "-e", "TORCHSIM_LOG_PATH=/workspace/results/raw_logs"
)

function Invoke-TorchSim {
  param([string]$Command)
  docker run --rm -it --ipc=host `
    -v "${repoDocker}:/workspace/PyTorchSim" `
    -v "${resultsDocker}:/workspace/results" `
    -w /workspace/PyTorchSim `
    @commonEnv `
    $Image bash -lc $Command
}

if ($Suite -eq "shell") {
  Invoke-TorchSim "bash"
}
elseif ($Suite -eq "smoke") {
  Invoke-TorchSim @"
set -e
mkdir -p /workspace/results/raw_logs
python experiments/gemm.py --size 128 128 128
python experiments/conv.py --size 1 32 32 320 320 3 1 1
python experiments/softmax.py --size 512 512
python tests/Diffusion/test_diffusion.py
"@
}
elseif ($Suite -eq "diffusion") {
  Invoke-TorchSim "python tests/Diffusion/test_diffusion.py"
}
