# 第一周本科生任务包

目标：让 5 位同学在不接触 RTL 的情况下，批量产出可检查、可合并、可接入 FLOOD simulator 的 workload 数据。

## 总原则

你们只负责重复性数据生产：

```text
trace -> workload CSV -> PyTorchSim baseline -> 检查报告 -> 运行记录
```

不需要做：

```text
RTL 仿真
FLOOD 架构判断
论文结论判断
性能百分比解释
```

这些由负责人统一做。

## 本周共同交付物

每位同学最终提交一个文件夹：

```text
week1_submit/<姓名或编号>/
  workload.csv
  run_notes.md
  check_report.md
  logs/
```

`workload.csv` 必须通过检查脚本。

## 5 人分工

| 人员 | 任务 | 重点模型/算子 | 最低交付 |
|---|---|---|---|
| 同学 1 | SD UNet Conv trace | Conv2d、down/up block、1x1/3x3 conv | 30 行 conv workload |
| 同学 2 | DiT GEMM/Attention trace | QKV、attention score、attention value、MLP | 30 行 gemm workload |
| 同学 3 | Softmax/Norm/非 MAC 记录 | Softmax、LayerNorm、GroupNorm、residual/add | 20 行 softmax/other 记录 |
| 同学 4 | PyTorchSim baseline 运行 | 跑同学 1/2/3 的 workload baseline cycles | cycles 填入 workload CSV |
| 同学 5 | 数据检查与汇总 | 字段检查、重复行、shape 格式、日志整理 | 总 check report 和合并表 |

## CSV 字段

本周统一使用：

```csv
id,model,stage,operator,shape_args,pytorchsim_cycles,latency_us,notes
```

字段解释：

| 字段 | 说明 |
|---|---|
| `id` | 唯一编号，如 `sd_unet_conv_001` |
| `model` | 模型名，如 `SD_UNet`、`DiT_B4` |
| `stage` | 层所在阶段，如 `down`、`mid_attn`、`mlp` |
| `operator` | 只能填 `conv`、`gemm`、`softmax` |
| `shape_args` | 形状字符串，规则见下方 |
| `pytorchsim_cycles` | PyTorchSim 输出周期；未跑先留空 |
| `latency_us` | 可留空，由负责人统一计算 |
| `notes` | 异常、来源、日志路径 |

## shape_args 规则

### conv

```text
B H W IC OC K S P
```

示例：

```text
1 64 64 320 320 3 1 1
```

### gemm

```text
M K N
```

示例：

```text
4096 320 320
```

### softmax

```text
N
```

示例：

```text
1024
```

## 检查方法

在仓库根目录运行：

```bash
python team_templates/validate_workload_csv.py week1_submit/你的编号/workload.csv --report week1_submit/你的编号/check_report.md
```

通过标准：

```text
PASS
```

如果失败，不要改检查脚本，按报告修改 CSV。

注意：

```text
trace 草稿阶段可以暂时留空 pytorchsim_cycles；
最终提交给负责人前必须填好 pytorchsim_cycles，否则检查不会通过。
```

## 命名规范

建议 id：

```text
sd_unet_conv_001
sd_unet_gemm_001
dit_b4_qkv_001
dit_b4_attn_score_001
dit_b4_mlp_001
softmax_001
```

不要使用中文、空格或重复 id。

## 运行记录

每次运行都要复制一份：

```text
team_templates/run_notes_template.md
```

至少记录：

- 日期；
- 服务器；
- 命令；
- 输入文件；
- 输出文件；
- 是否成功；
- 失败截图或错误摘要。

## 本周验收标准

本周不要求论文结论，只验收数据质量：

1. 每位同学的 `workload.csv` 字段齐全；
2. shape 格式正确；
3. id 不重复；
4. 至少一半行有 PyTorchSim cycles；
5. 每次运行有 notes/log；
6. check report 通过或明确列出未通过原因。

## 负责人后续处理

负责人会把通过检查的 CSV 接入：

```text
PyTorchSim baseline
  -> FLOOD projection
  -> B/C/D readiness
  -> 抽样 RTL validation
```

本科生不需要判断数据能否进论文主表。
