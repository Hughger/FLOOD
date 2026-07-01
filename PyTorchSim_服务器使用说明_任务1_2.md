# PyTorchSim 服务器使用说明（任务 1/2 负责人版）

更新时间：2026-07-01

适用对象：

```text
任务 1：CNN / UNet / Conv 类 PyTorchSim 运行负责人
任务 2：Transformer / Attention / GEMM 类 PyTorchSim 运行负责人
```

本文目标是让没有经验的同学也能按统一流程在服务器上运行 PyTorchSim，并产出可合并、可复现的 workload 数据。

## 1. 你们要完成什么

你们不需要理解 FLOOD RTL，也不需要改代码。

你们只需要完成三件事：

```text
1. 在服务器上运行 PyTorchSim workload
2. 把每层结果整理成统一 CSV
3. 记录运行命令、日志和问题
```

最终交付物：

```text
person1_pytorchsim_cnn.csv
person2_pytorchsim_transformer.csv
run_notes.md
对应 log 文件
```

## 2. 登录服务器

服务器地址、端口、私钥位置不要写进公开仓库，请从飞书内部获取。

登录命令格式：

```bash
ssh -i <你的私钥路径> -p <端口> root@<服务器地址>
```

示例格式：

```bash
ssh -i ./your_key -p 12345 root@example.server.com
```

如果第一次连接出现：

```text
Are you sure you want to continue connecting?
```

输入：

```text
yes
```

如果提示：

```text
Permission denied
```

说明私钥、端口、用户名或服务器地址有问题，先不要继续试，截图发给负责人。

## 3. 服务器目录

登录后，先进入工作目录：

```bash
cd /root/autodl-tmp/torchsim_work
```

常用目录：

```text
/root/autodl-tmp/torchsim_work/PyTorchSim
/root/autodl-tmp/torchsim_work/flood_results
/root/autodl-tmp/torchsim_work/logs
```

如果目录不存在，先执行：

```bash
ls /root/autodl-tmp/torchsim_work
```

然后把截图或输出发给负责人，不要自己乱建目录。

## 4. 每次运行前先检查环境

进入服务器后先执行：

```bash
cd /root/autodl-tmp/torchsim_work
pwd
python3 --version
ls
```

再检查 PyTorchSim 是否存在：

```bash
ls /root/autodl-tmp/torchsim_work/PyTorchSim
```

如果能看到 PyTorchSim 文件夹，继续下一步。

如果看不到，记录：

```text
PyTorchSim directory missing
```

然后联系负责人。

## 5. 任务 1：CNN / UNet / Conv 类 workload

任务 1 负责人主要跑卷积类 workload。

你需要优先收集这些类型：

```text
UNet conv
ResNet conv
MobileNet conv
CNN small / medium conv
Diffusion UNet conv proxy
```

最终统一记成 `conv` 算子。

conv 的 shape 格式固定为：

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

示例：

```text
1 64 64 320 320 3 1 1
```

表示：

```text
batch=1
input feature map=64x64
input channels=320
output channels=320
kernel=3x3
stride=1
padding=1
```

CSV 示例：

```csv
id,model,stage,operator,shape_args,pytorchsim_cycles,latency_us,notes
unet_conv_001,SD_UNet,down,conv,"1 64 64 320 320 3 1 1",187707,199.68,
```

## 6. 任务 2：Transformer / Attention / GEMM 类 workload

任务 2 负责人主要跑矩阵乘类 workload。

你需要优先收集这些类型：

```text
QKV projection
attention score GEMM
attention value GEMM
Transformer MLP fc1
Transformer MLP fc2
ViT / BERT / Diffusion attention proxy
```

最终统一记成 `gemm` 算子。

gemm 的 shape 格式固定为：

```text
M K N
```

示例：

```text
4096 320 320
```

表示：

```text
M=4096
K=320
N=320
```

CSV 示例：

```csv
id,model,stage,operator,shape_args,pytorchsim_cycles,latency_us,notes
attn_qkv_001,SD_UNet,attention,gemm,"4096 320 320",34810,37.03,
```

## 7. 推荐运行方式

如果负责人已经提供了现成运行脚本，优先使用脚本。

在本项目中，本地已有一些远程运行脚本模板：

```text
codex_remote_torchsim_check.sh
codex_remote_torchsim_validate.sh
codex_remote_torchsim_build_core.sh
codex_remote_torchsim_download_assets.sh
```

服务器上如果有对应脚本，可以按负责人给出的命令执行。

通用运行格式：

```bash
cd /root/autodl-tmp/torchsim_work/PyTorchSim
<运行命令> > /root/autodl-tmp/torchsim_work/logs/<任务名>.log 2>&1
```

示例：

```bash
cd /root/autodl-tmp/torchsim_work/PyTorchSim
python3 your_run_script.py > /root/autodl-tmp/torchsim_work/logs/person1_unet_conv.log 2>&1
```

注意：

```text
不要直接关闭窗口。
不要边跑边改脚本。
不要覆盖别人的 log。
```

## 8. 长任务怎么跑

如果任务预计超过 10 分钟，建议用 `nohup` 后台运行：

```bash
cd /root/autodl-tmp/torchsim_work/PyTorchSim
nohup python3 your_run_script.py > /root/autodl-tmp/torchsim_work/logs/<任务名>.log 2>&1 &
```

查看任务是否还在跑：

```bash
ps -eo pid,etime,pcpu,pmem,cmd | grep python | grep -v grep
```

查看日志最后 50 行：

```bash
tail -50 /root/autodl-tmp/torchsim_work/logs/<任务名>.log
```

如果看到错误，不要反复重跑，先把最后 50 行日志复制到运行记录里。

## 9. 输出 CSV 标准

所有人最后都要交统一格式 CSV：

```csv
id,model,stage,operator,shape_args,pytorchsim_cycles,latency_us,notes
```

字段说明：

| 字段 | 说明 |
|---|---|
| `id` | 唯一编号，不能重复 |
| `model` | 模型名 |
| `stage` | 模型阶段，例如 down / up / attention / mlp |
| `operator` | 只能使用统一名称，例如 `conv` / `gemm` |
| `shape_args` | 标准 shape 参数 |
| `pytorchsim_cycles` | PyTorchSim 输出周期 |
| `latency_us` | 延迟，没有可留空 |
| `notes` | 备注 |

正确示例：

```csv
unet_conv_001,SD_UNet,down,conv,"1 64 64 320 320 3 1 1",187707,199.68,
attn_qkv_001,SD_UNet,attention,gemm,"4096 320 320",34810,37.03,
```

错误示例：

```csv
conv1,unet,down,卷积,"64x64 320 320",187707,,
```

错误原因：

```text
operator 不能写中文
shape_args 没有按 B H W IC OC K S P
id 不够清晰
```

## 10. 运行记录模板

每次运行都要写运行记录。

文件名示例：

```text
20260701_unet_conv_run_notes.md
```

模板：

```md
# 运行记录

负责人：
日期：
任务编号：
模型/任务：
服务器：
工作目录：
使用脚本：
输入文件：
输出文件：
日志文件：

## 运行命令

```bash
填入实际运行命令
```

## 输出结果

生成文件：
- xxx.csv
- xxx.log

## 是否成功

成功 / 失败

## 失败或异常记录

如果失败，贴最后 50 行错误日志。

## 备注

需要负责人确认的问题写在这里。
```

## 11. 每天交付什么

每天结束前，每个人至少提交：

```text
1. 当天 CSV
2. 当天 run_notes.md
3. 对应 log 文件
```

目录建议：

```text
team_outputs/person1/
  outputs/
  logs/
  notes/

team_outputs/person2/
  outputs/
  logs/
  notes/
```

## 12. 常见问题

### 12.1 SSH 连不上

可能原因：

```text
服务器地址错
端口错
私钥错
服务器过期
网络问题
```

处理方式：

```text
不要重复试太多次。
截图发给负责人。
```

### 12.2 Permission denied

可能是私钥没权限或不是对应服务器的 key。

处理方式：

```text
把完整报错截图发给负责人。
不要把私钥内容发群里。
```

### 12.3 找不到 PyTorchSim 目录

先执行：

```bash
ls /root/autodl-tmp/torchsim_work
```

然后把输出发给负责人。

### 12.4 跑出来 cycles 是空的

处理方式：

```text
检查 log 是否有 error。
检查任务是否真的跑完。
不要自己手填 cycles。
```

### 12.5 shape 不知道怎么填

处理方式：

```text
先把原始层信息写到 notes。
把截图或模型层参数发给 3 号数据整理员或负责人。
```

## 13. 禁止事项

任务 1/2 负责人第一阶段不要做这些事：

```text
不要修改 FLOOD RTL。
不要修改 MacMachineWrapper.v。
不要修改校准公式。
不要手动编造 cycles。
不要改别人的 CSV。
不要覆盖别人的 log。
不要上传私钥、密码、服务器 token。
不要自己创造新的 CSV 格式。
```

## 14. 合格标准

一次任务合格，需要满足：

```text
CSV 能打开。
CSV 列名正确。
operator 只使用统一名称。
shape_args 格式正确。
pytorchsim_cycles 不为空。
有运行记录。
有 log。
失败任务有错误日志。
```

如果不满足以上标准，需要重新整理后再提交。

## 15. 给任务 1/2 负责人的一句话

你们的核心任务不是解释结果，而是把 PyTorchSim workload 数据稳定、规范、可复现地跑出来。

只要做到：

```text
命令清楚
日志保留
CSV 格式正确
cycles 真实
```

后续 FLOOD 换算、RTL 校准和论文分析可以由负责人和 Codex 继续完成。

