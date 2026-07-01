# FLOOD / PyTorchSim 团队分工与执行说明

更新时间：2026-07-01

## 1. 项目目标

本阶段目标是让多人协作扩大 FLOOD / PyTorchSim 的实验数据覆盖面，并为后续论文实验准备可复现的数据。

整体工作流如下：

```text
收集模型 / 层参数
        ↓
运行 PyTorchSim baseline
        ↓
整理成统一 CSV
        ↓
用 FLOOD 脚本进行换算 / projection
        ↓
筛选代表性层
        ↓
进行 RTL 验证 / 校准
        ↓
生成论文表格和图
```

简单理解：

- PyTorchSim 负责提供 baseline 数据。
- FLOOD 脚本负责把 workload 换算到 FLOOD 架构。
- RTL 验证负责检查 FLOOD 模型和真实硬件 RTL 是否一致。
- 团队成员主要负责跑数据、整理数据、检查格式和生成材料。

## 2. 分工原则

由于大家目前都没有相关经验，第一阶段不要求理解 RTL 或 NPU 细节。

新人优先做：

```text
重复性强、格式明确、容易检查的工作
```

暂时不要做：

```text
修改 RTL、修改校准公式、改复杂脚本、自己设计数据格式
```

所有实验必须满足：

1. 有输入文件。
2. 有运行命令。
3. 有输出文件。
4. 有运行记录。
5. 结果格式统一。

## 3. 五人分工

## 3.1 1 号同学：PyTorchSim 运行员 A

### 负责方向

CNN / UNet / 卷积类 workload。

### 主要任务

1. 按照给定模板运行 PyTorchSim。
2. 记录每一层的算子类型和 shape。
3. 导出 PyTorchSim baseline cycles。
4. 保留运行日志和输出文件。

### 建议负责模型

```text
UNet conv
ResNet conv
MobileNet conv
CNN small / medium workload
Diffusion UNet conv proxy
```

### 交付物

```text
outputs/person1_pytorchsim_cnn.csv
outputs/person1_run_notes.md
logs/person1_xxx.log
```

### 不需要做

- 不需要理解 FLOOD RTL。
- 不需要修改脚本。
- 不需要判断结果好坏。

## 3.2 2 号同学：PyTorchSim 运行员 B

### 负责方向

Transformer / Attention / GEMM 类 workload。

### 主要任务

1. 运行 attention 和 GEMM 相关 workload。
2. 记录每一层的矩阵规模。
3. 导出 PyTorchSim baseline cycles。
4. 保留运行日志。

### 建议负责模型

```text
QKV projection
attention score GEMM
attention value GEMM
MLP fc1 / fc2
ViT
BERT
Diffusion attention proxy
```

### 交付物

```text
outputs/person2_pytorchsim_transformer.csv
outputs/person2_run_notes.md
logs/person2_xxx.log
```

## 3.3 3 号同学：数据整理员

### 负责方向

统一格式、检查数据、合并 CSV。

### 主要任务

1. 收集 1 号和 2 号的 CSV。
2. 检查列名是否一致。
3. 检查 shape 格式是否正确。
4. 检查 cycles 是否为空。
5. 删除重复数据。
6. 合并成一个总表。

### 统一 CSV 格式

```csv
id,model,stage,operator,shape_args,pytorchsim_cycles,latency_us,notes
unet_conv_001,SD_UNet,down,conv,"1 64 64 320 320 3 1 1",187707,199.68,
attn_qkv_001,SD_UNet,attention,gemm,"4096 320 320",34810,37.03,
```

### shape_args 规范

conv 固定格式：

```text
B H W IC OC K S P
```

含义：

```text
B  = batch size
H  = input height
W  = input width
IC = input channels
OC = output channels
K  = kernel size
S  = stride
P  = padding
```

gemm 固定格式：

```text
M K N
```

含义：

```text
M = 矩阵 M 维度
K = reduction 维度
N = 输出 N 维度
```

### 交付物

```text
outputs/merged_workload.csv
outputs/data_check_report.md
```

### 检查报告需要包含

```text
总行数：
conv 行数：
gemm 行数：
缺失 cycles 的行：
shape 格式错误的行：
重复 id：
需要人工确认的问题：
```

## 3.4 4 号同学：FLOOD 换算员

### 负责方向

使用已有脚本把 PyTorchSim workload 换算成 FLOOD projection。

### 主要任务

1. 接收 `merged_workload.csv`。
2. 运行 FLOOD 映射脚本。
3. 生成 FLOOD projection 结果。
4. 汇总不同算子类型的结果。
5. 挑选候选 RTL 验证层。

### 输入文件

```text
outputs/merged_workload.csv
```

### 输出文件

```text
outputs/flood_projection_details.csv
outputs/flood_projection_summary.csv
outputs/candidate_rtl_layers.md
```

### 候选 RTL 层筛选标准

优先选择：

1. PyTorchSim cycles 高的层。
2. FLOOD projection 变化大的层。
3. 不同类型都要覆盖。

建议至少覆盖：

```text
k=1 pointwise conv
k=3 spatial conv
gemm
attention gemm
```

### 不需要做

- 不修改 FLOOD 模型公式。
- 不修改 RTL。
- 不自行解释论文结论。

## 3.5 5 号同学：文档和图表整理员

### 负责方向

把实验结果整理成人能看懂的周报、表格和图。

### 主要任务

1. 整理每周完成了哪些实验。
2. 汇总 PyTorchSim 和 FLOOD projection 结果。
3. 画简单统计图。
4. 整理论文候选表格。
5. 记录当前问题和下一步计划。

### 交付物

```text
docs/weekly_summary.md
figures/workload_operator_breakdown.png
figures/flood_vs_pytorchsim_summary.png
tables/main_projection_table.csv
```

### 每周总结需要包含

```text
本周跑了哪些模型：
新增多少行 workload：
conv / gemm / attention 各多少：
PyTorchSim 总 cycles：
FLOOD projection 总 cycles：
候选 RTL 验证层：
遇到的问题：
下周计划：
```

## 4. 第一周执行计划

## 第 1 天：统一培训和环境确认

目标：

```text
所有人知道自己负责什么，知道输出格式，不要求理解底层原理。
```

需要完成：

1. 每个人阅读本分工文档。
2. 每个人确认自己能访问工作目录。
3. 每个人领取自己的任务。
4. 确认 CSV 模板和运行记录模板。

## 第 2-3 天：小样例试跑

目标：

```text
先跑少量 case，验证流程和格式。
```

任务：

- 1 号跑 3-5 个 CNN / conv case。
- 2 号跑 3-5 个 GEMM / attention case。
- 3 号检查格式。
- 4 号尝试用小 CSV 跑 FLOOD projection。
- 5 号开始整理第一版周报模板。

## 第 4 天：数据合并和检查

目标：

```text
生成第一版 merged_workload.csv。
```

任务：

- 3 号合并 CSV。
- 3 号输出 data_check_report.md。
- 所有人根据检查报告修正自己的数据。

## 第 5 天：FLOOD projection

目标：

```text
生成第一版 FLOOD vs PyTorchSim 对比结果。
```

任务：

- 4 号运行 projection 脚本。
- 4 号输出 summary。
- 4 号列出 candidate_rtl_layers.md。

## 第 6-7 天：总结和复盘

目标：

```text
形成一份可以给老师或师兄看的周报。
```

任务：

- 5 号整理周报。
- 负责人审核结果。
- 决定下一周扩大哪些 workload。
- 决定是否挑 1-2 个层做 RTL 验证。

## 5. 文件命名规范

每个人的文件统一放在自己的目录下：

```text
team_outputs/person1/
team_outputs/person2/
team_outputs/person3/
team_outputs/person4/
team_outputs/person5/
```

建议结构：

```text
team_outputs/person1/
  outputs/
  logs/
  notes/
```

文件命名建议：

```text
日期_模型_任务.csv
日期_模型_运行记录.md
日期_模型.log
```

示例：

```text
20260701_unet_conv_pytorchsim.csv
20260701_unet_conv_run_notes.md
20260701_unet_conv.log
```

## 6. 运行记录模板

每次运行都要写运行记录：

```md
# 运行记录

负责人：
日期：
模型/任务：
使用脚本：
输入文件：
输出文件：

## 运行命令

```bash
填入实际命令
```

## 输出结果

生成文件：
- xxx.csv
- xxx.log

## 是否成功

成功 / 失败

## 问题记录

如果失败，贴最后 20 行错误。
```

## 7. CSV 模板

统一使用下面格式：

```csv
id,model,stage,operator,shape_args,pytorchsim_cycles,latency_us,notes
example_conv,UNet,down,conv,"1 64 64 320 320 3 1 1",187707,199.68,
example_gemm,Attention,qkv,gemm,"4096 320 320",34810,37.03,
```

字段说明：

| 字段 | 说明 |
|---|---|
| `id` | 唯一编号，不要重复 |
| `model` | 模型名 |
| `stage` | 层所在阶段 |
| `operator` | 算子类型，例如 `conv` / `gemm` |
| `shape_args` | 标准 shape 参数 |
| `pytorchsim_cycles` | PyTorchSim 输出周期 |
| `latency_us` | 延迟，如果没有可留空 |
| `notes` | 备注 |

## 8. 禁止事项

第一阶段所有新人禁止做：

```text
不要修改 RTL。
不要修改 MacMachineWrapper.v。
不要修改校准公式。
不要修改 Git 主分支结构。
不要自己创造 CSV 格式。
不要手动编造 cycles。
不要删除别人的结果。
不要把私钥、密码、服务器登录信息上传。
```

如果不确定，先问负责人。

## 9. 验收标准

每个人的任务是否合格，按以下标准检查。

### PyTorchSim 运行员

合格标准：

```text
有 CSV。
有运行记录。
有 log。
cycles 不为空。
shape_args 格式正确。
```

### 数据整理员

合格标准：

```text
merged_workload.csv 能被脚本读取。
没有重复 id。
没有缺失 operator。
没有明显错误 shape。
有 data_check_report.md。
```

### FLOOD 换算员

合格标准：

```text
能生成 projection details。
能生成 projection summary。
能列出候选 RTL 层。
不改模型公式。
```

### 文档图表员

合格标准：

```text
周报能说明本周做了什么。
表格能看懂。
图能说明问题。
问题和下周计划清楚。
```

## 10. 负责人需要做的事

负责人不需要亲自跑所有数据，主要负责：

1. 分配任务。
2. 审核 CSV 格式。
3. 判断哪些结果可信。
4. 选择 RTL 验证层。
5. 和 Codex 一起处理复杂脚本、RTL、Git 和论文材料。

负责人每周需要确认：

```text
数据是否可复现？
结果是否格式统一？
projection 是否能跑通？
是否有值得 RTL 验证的代表层？
是否能形成论文材料？
```

## 11. 当前推荐安排

最终人员安排如下：

```text
1 号：跑 CNN / UNet / conv 类 PyTorchSim
2 号：跑 Transformer / Attention / GEMM 类 PyTorchSim
3 号：合并和检查 CSV
4 号：跑 FLOOD projection 脚本
5 号：整理文档、表格和图
```

负责人负责：

```text
确定测试方向
审核结果
挑选 RTL 验证层
处理复杂问题
维护 Git 和最终结果包
```

## 12. 最终产出目标

第一阶段结束时，至少应形成：

```text
merged_workload.csv
flood_projection_summary.csv
candidate_rtl_layers.md
weekly_summary.md
main_projection_table.csv
```

第二阶段再进一步形成：

```text
RTL measured vs calibrated model 表
完整 workload calibrated projection 表
论文图表草稿
```

