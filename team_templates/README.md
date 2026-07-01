# 团队测试模板

本目录给任务 1/2/3 同学使用，用于统一 PyTorchSim workload 数据格式。

## 文件说明

| 文件 | 用途 |
|---|---|
| `workload_template.csv` | workload CSV 模板 |
| `run_notes_template.md` | 每次运行的记录模板 |
| `validate_workload_csv.py` | 自动检查 CSV 格式 |

## CSV 格式

统一列名：

```csv
id,model,stage,operator,shape_args,pytorchsim_cycles,latency_us,notes
```

`operator` 目前只允许：

```text
conv
gemm
softmax
```

其中 `softmax` 可以先记录，但暂时不作为 FLOOD 主要映射对象。

## shape_args 规则

conv：

```text
B H W IC OC K S P
```

gemm：

```text
M K N
```

softmax：

```text
N
```

## 检查 CSV

在仓库根目录运行：

```bash
python team_templates/validate_workload_csv.py your_workload.csv --report your_check_report.md
```

如果本机没有 `python`，把 CSV 发给负责人统一检查。

检查通过时会显示：

```text
PASS
```

检查失败时会列出错误行号和原因。
