#!/usr/bin/env python3
"""
生成testbench.v所需的权重和特征图Hex文件
基于DataConverter的数据组织方式
"""

import os
import sys
import csv
import argparse
import numpy as np

ROW_SIZE = 4
COL_SIZE = 4

def convert_weights_csv(path: str, cout: int, cinIdxTotal: int, k: int, groupSize: int):
    # 参考 Scala DataConverter.convertWeights 的重排：
    # 输出二维数组： [cout * cinIdxTotal * k * k * groupSize][ROW_SIZE]
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    # 读取 CSV，按空行分块：[cout][cin][k][k]
    with open(path, 'r', newline='') as f:
        lines = [ln.rstrip('\n') for ln in f]
    weights4D = []
    currentCout = []
    currentCin = []
    prevEmpty = False
    for ln in lines:
        t = ln.strip()
        if t == '':
            if currentCout and prevEmpty:
                weights4D.append(currentCout)
                currentCout = []
            elif currentCin and not prevEmpty:
                currentCout.append(currentCin)
                currentCin = []
            prevEmpty = True
        else:
            vals = [int(x.strip()) for x in t.split(',') if x.strip()]
            currentCin.append(vals)
            prevEmpty = False
    if currentCin:
        currentCout.append(currentCin)
    if currentCout:
        weights4D.append(currentCout)

    # 按最新Wrapper：每个权重向量长度为ROW_SIZE；输入通道数=ROW_SIZE*groupSize 每个 cinIdx
    cin = cinIdxTotal * ROW_SIZE * groupSize
    out = np.zeros((cout * cinIdxTotal * k * k * groupSize, ROW_SIZE), dtype=np.int32)
    addr = 0
    for idx in range(cinIdxTotal):
        for c in range(cout):
            for y in range(k):
                for x in range(k):
                    for g in range(groupSize):
                        for i in range(ROW_SIZE):
                            out[addr][i] = weights4D[c][idx*ROW_SIZE*groupSize+g*ROW_SIZE+i][y][x]
                        addr += 1
    return out.tolist()

def convert_features_csv(path: str, cinIdxTotal: int, height: int, width: int, groupSize: int):
    # 参考 Scala DataConverter.convertFeatures（按列/组重排后的一维地址行）
    # 输出二维数组：[height * (cinIdxTotal*ROW_SIZE*groupSize)][width]
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, 'r', newline='') as f:
        lines = [ln.rstrip('\n') for ln in f]
    features3D = []
    currentCin = []
    currentRow = []
    prevEmpty = False
    for ln in lines:
        t = ln.strip()
        if t == '':
            if currentCin:
                features3D.append(currentCin)
                currentCin = []
            prevEmpty = True
        else:
            vals = [int(x.strip()) for x in t.split(',') if x.strip()]
            currentCin.append(vals)
            prevEmpty = False
    if currentRow:
        currentCin.append(currentRow)
    if currentCin:
        features3D.append(currentCin)

    cin = cinIdxTotal * ROW_SIZE * groupSize
    out = np.zeros((height * cin, width), dtype=np.int32)
    addr = 0
    for idx in range(cinIdxTotal):
        for g in range(groupSize):
            for c in range(ROW_SIZE):
                for y in range(height):
                    for x in range(width):
                        globalCinIdx = idx*ROW_SIZE*groupSize + g*ROW_SIZE + c
                        val = 0
                        if globalCinIdx < len(features3D):
                            ch = features3D[globalCinIdx]
                            if y < len(ch):
                                row = ch[y]
                                if x < len(row):
                                    val = row[x]
                        out[addr][x] = val
                    addr += 1
    return out.tolist()

def generate_weights_hex(project_root: str):
    """生成权重Hex文件"""
    print("=== 生成权重Hex文件 ===")
    
    # 参数（与WrapperTest一致）
    k = 3
    cout = 2
    cinIdxTotal = 2
    groupSize = 2
    
    # 检查权重CSV文件是否存在
    weights_csv = os.path.join(project_root, "src", "python", "weights.csv")
    if not os.path.exists(weights_csv):
        print(f"警告: {weights_csv} 不存在，使用默认权重数据")
        weights_data = generate_default_weights(cout, cinIdxTotal, k, groupSize)
    else:
        weights_data = convert_weights_csv(weights_csv, cout, cinIdxTotal, k, groupSize)
    
    # 生成ping和pong权重文件
    generate_hex_file(weights_data, "weights_ping.hex", "权重Ping", line_bits=32)
    # generate_hex_file(weights_data, "weights_pong.hex", "权重Pong") # 暂时只使用ping
    
    return weights_data

def generate_features_hex(project_root: str):
    """生成整体特征图Hex文件（不按tile拆分）"""
    print("=== 生成特征图Hex文件 ===")
    
    # 参数（与WrapperTest一致）
    cinIdxTotal = 2
    resolutionRowIdxTotal = 2
    resolutionColIdxTotal = 2
    colSize = 4
    groupSize = 2
    groupNum = 2  # tileSize/groupSize = 4/2 = 2
    
    height = groupNum * resolutionRowIdxTotal
    width = colSize * resolutionColIdxTotal
    
    # 检查特征图CSV文件是否存在
    features_csv = os.path.join(project_root, "src", "python", "features.csv")
    if not os.path.exists(features_csv):
        print(f"警告: {features_csv} 不存在，使用默认特征图数据")
        features_data = generate_default_features(cinIdxTotal, height, width, groupSize)
    else:
        features_data = convert_features_csv(features_csv, cinIdxTotal, height, width, groupSize)
    
    # 生成单一整体特征图文件 features.hex
    # 每行包含 width 个8位元素 → line_bits = width * 8
    generate_hex_file(features_data, "features.hex", "特征图(整体)", line_bits=width*8)
    
    return features_data

def generate_default_weights(cout, cinIdxTotal, k, groupSize):
    """生成默认权重数据"""
    print("生成默认权重数据...")
    
    # 权重数据格式: [cout * cinIdxTotal * k * k * groupSize][ROW_SIZE]
    rowSize = ROW_SIZE
    total_addrs = cout * cinIdxTotal * k * k * groupSize
    weights = np.zeros((total_addrs, rowSize), dtype=np.int32)
    
    # 填充一些测试数据
    for addr in range(total_addrs):
        for i in range(rowSize):
            weights[addr][i] = (addr * rowSize + i) % 256 - 128  # -128到127范围
    
    return weights.tolist()

def generate_default_features(cinIdxTotal, height, width, groupSize):
    """生成默认特征图数据"""
    print("生成默认特征图数据...")
    
    # 特征图数据格式: [height * cin][width]
    rowSize = ROW_SIZE
    cin = cinIdxTotal * rowSize * groupSize
    total_addrs = height * cin
    features = np.zeros((total_addrs, width), dtype=np.int32)
    
    # 填充一些测试数据
    for addr in range(total_addrs):
        for col in range(width):
            features[addr][col] = (addr * width + col) % 256 - 128  # -128到127范围
    
    return features.tolist()

# 已弃用：按tile拆分不再生成

def generate_hex_file(data, filename, description, line_bits: int = 32):
    """生成Hex文件"""
    print(f"生成 {description} 文件: {filename}")
    
    with open(filename, 'w') as f:
        for row in data:
            # 将每行数据打包成 line_bits 位（按低位在前的顺序拼接，每元素8位）
            packed = 0
            for i, val in enumerate(row):
                unsigned_val = val & 0xFF
                packed |= (unsigned_val << (i * 8))
            # 计算最少需要的hex位数
            hex_digits = (line_bits + 3) // 4
            f.write(f"{packed:0{hex_digits}x}\n")

def main():
    """主函数"""
    print("=== 生成testbench.v测试数据 ===")

    parser = argparse.ArgumentParser(description="生成 Verilog 测试所需 HEX 数据")
    parser.add_argument("--root", dest="project_root", default=None, help="项目根目录，例如 E:/Projects/SNN/FLOOD_Accelerator/1.design_files/flood_accelerator")
    # 可重构参数（参考 WrapperTest.scala 与 python 生成脚本习惯）
    parser.add_argument("--k", type=int, default=3, help="kernel size k")
    parser.add_argument("--cout", type=int, default=2, help="输出通道数 cout")
    parser.add_argument("--cin-idx-total", type=int, default=2, help="cinIdxTotal")
    parser.add_argument("--group-size", type=int, default=2, help="组内 tile 数 groupSize")
    parser.add_argument("--res-rows", type=int, default=2, help="resolutionRowIdxTotal")
    parser.add_argument("--res-cols", type=int, default=2, help="resolutionColIdxTotal")
    parser.add_argument("--row-size", type=int, default=4, help="ROW_SIZE 配置")
    parser.add_argument("--col-size", type=int, default=4, help="COL_SIZE 配置")
    # 与 ./src/python/generate_test_data.py 保持一致：不传 tileSize，传 groupNum
    parser.add_argument("--group-num", type=int, default=2, help="groupNum 配置 (tileSize/groupSize)")
    parser.add_argument("--features-csv", default=None, help="features.csv 路径(可选) 相对或绝对")
    parser.add_argument("--weights-csv", default=None, help="weights.csv 路径(可选) 相对或绝对")
    args = parser.parse_args()
    
    # 切换到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 解析项目根目录
    project_root = args.project_root
    if project_root is None:
        # 默认取三层上级目录作为根
        project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
    print(f"[INFO] 使用项目根目录: {project_root}")

    # 覆盖全局 ROW/COL 参数
    global ROW_SIZE, COL_SIZE
    ROW_SIZE = int(args.row_size)
    COL_SIZE = int(args.col_size)
    
    # 覆盖 CSV 路径（如果提供）
    if args.weights_csv:
        custom_w = args.weights_csv if os.path.isabs(args.weights_csv) else os.path.join(project_root, args.weights_csv)
        os.makedirs(os.path.dirname(custom_w), exist_ok=True)
        # 覆盖内部使用路径
        def _wrap_generate_weights_hex(project_root_inner: str):
            nonlocal custom_w
            def inner_path(_):
                return custom_w
            return inner_path
        # 直接把路径传递到 convert 函数时使用（下方直接传参替代）

    # 生成权重Hex文件
    weights_data = None
    w_csv = args.weights_csv if args.weights_csv else os.path.join(project_root, "src", "python", "weights.csv")
    if os.path.exists(w_csv):
        weights_data = convert_weights_csv(w_csv, args.cout, args.cin_idx_total, args.k, args.group_size)
        # 每行包含 ROW_SIZE 个8位权重 → line_bits = ROW_SIZE * 8（与 Wrapper 256bit/512bit 接口一致性）
        generate_hex_file(weights_data, "weights_ping.hex", "权重Ping", line_bits=ROW_SIZE*8)
    else:
        print(f"警告: {w_csv} 不存在，使用默认权重数据")
        weights_data = generate_default_weights(args.cout, args.cin_idx_total, args.k, args.group_size)
        generate_hex_file(weights_data, "weights_ping.hex", "权重Ping", line_bits=ROW_SIZE*8)
    
    # 生成特征图Hex文件
    features_data = None
    # 高度: groupNum * resRows（由参数直接给出 groupNum）
    group_num = args.group_num
    height = group_num * args.res_rows
    width = args.col_size * args.res_cols
    f_csv = args.features_csv if args.features_csv else os.path.join(project_root, "src", "python", "features.csv")
    if os.path.exists(f_csv):
        features_data = convert_features_csv(f_csv, args.cin_idx_total, height, width, args.group_size)
        generate_hex_file(features_data, "features.hex", "特征图(整体)", line_bits=width*8)
    else:
        print(f"警告: {f_csv} 不存在，使用默认特征图数据")
        features_data = generate_default_features(args.cin_idx_total, height, width, args.group_size)
        generate_hex_file(features_data, "features.hex", "特征图(整体)", line_bits=width*8)
    
    print("=== 生成完成 ===")
    print(f"权重数据形状: {len(weights_data)} x {len(weights_data[0]) if weights_data else 0}")
    print(f"特征图数据形状: {len(features_data)} x {len(features_data[0]) if features_data else 0}")
    
    # 列出生成的文件
    hex_files = [f for f in os.listdir('.') if f.endswith('.hex')]
    print(f"生成的Hex文件: {hex_files}")

if __name__ == "__main__":
    main()
