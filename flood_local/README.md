# FLOOD PyTorchSim 本地运行入口

这个目录是 FLOOD HPCA PyTorchSim 测试方案的本地入口。
它不修改 PyTorchSim 内部代码，只封装官方 Docker 运行流程，
把日志统一放到 `results/` 下，并提供第一阶段的最小算子闭环测试。

## 当前本地状态

- PyTorchSim 仓库：`D:\work-yanjiusheng\HPCA\PyTorchSim`
- 上游提交：`509f42554202edb29cf8d31ddf619776f465e717`
- 官方推荐镜像：`ghcr.io/psal-postech/torchsim-ci:v1.1.0`
- 当前阻塞：这台 Windows 主机的 PATH 里还没有 Docker。

## 阶段 A：最小闭环

安装并启动 Docker Desktop 后，在 `D:\work-yanjiusheng\HPCA` 中运行：

```powershell
.\flood_local\run_pytorchsim.cmd -Suite smoke
```

该命令会依次运行：

- GEMM：`experiments/gemm.py --size 128 128 128`
- Conv：`experiments/conv.py --size 1 32 32 320 320 3 1 1`
- Softmax：`experiments/softmax.py --size 512 512`
- synthetic SD UNet block：`tests/Diffusion/test_diffusion.py`

然后整理日志：

```powershell
.\flood_local\run_pytorchsim.cmd -Suite collect
```

汇总 CSV 会写入：

```text
results/layer_results/cycles.csv
```

## 结果目录

```text
results/
  manifest.json
  hardware_config.yaml
  raw_logs/
  traces/
  layer_results/
  model_results/
  figures/
```

## 正式跑数注意事项

用于论文图表前，需要先冻结 `results/hardware_config.yaml`。
当前文件只是按测试方案准备的参数模板，不代表最终芯片参数。
`smoke` 套件只用于环境联调和数据链路打通，不能直接作为论文主结果。
