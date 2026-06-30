//////////////////////////////////////////////////////////////////////////////
// Copyright 2024 YDXS. All rights reserved.                                //
//                                                                          //
//                       __   _________   __ _____                          //
//                       \ \ / /  _  \ \ / //  ___|                         //
//                        \ V /| | | |\ V / \ `--.                          //
//                         \ / | | | |/   \  `--. \                         //
//                         | | | |/ // /^\ \/\__/ /                         //
//                         \_/ |___/ \/   \/\____/                          //
//                                                                          //
//////////////////////////////////////////////////////////////////////////////
// Project    : FLOOD_Accelerator                                           //
// Module     : OutRouterPlane.scala                                        //
// Author     : 陈挺然                                                      //
// Email      : 18073369150@buaa.edu.cn                                     //
// Description: 引入嵌入平面处理功能的Router模块，使用流水线方法进行数据（输入通道）补齐与（列、行向拼接）
// • 配置信息（通过APB总线写入）：
//   • 配置寄存器_0（结果图Block参数，一层卷积配置一次）（Block宽度默认为2（个字））
//     • k（卷积核窗口尺寸）
//     • groupSize（一组内的Tile数量）
//     • groupNum（Cluster内一共有几组）
//     • cout（输出结果图Block的通道数）
//     • cin（当前特征图Block的起始通道）
//     • workMode（工作模式）
//       • 一般列向起点(001): 表示特征图Block为非顶端最左侧,cin=0的Block
//       • 一般列向拼接(010)：表示特征图为非顶端非左侧,cin=0的Block
//       • 仅输入通道补齐(011)：表示特征图为cin!=0的Block
//       • 初始列向起点(000)：表示特征图位于最顶端最左侧,cin=0的Block
//       • 初始列向拼接(100)：表示特征图位于最顶端非最左侧,cin=0的Block
//       • 默认情况为不补齐也不拼接(000)：特征图为顶端最左侧，cin=0的Block
//     • resolutionCol（当前特征图Block在整个图像分辨率中的列索引，以colSize个像素为单位）
// • IO
//   • 继承OutRouter的IO，并扩展SRAM接口
// • 工作原理
//   • 输出缓存结构特点：
//     • 由outputSram与jointSram两个缓存组成
//       • 二者相同之处：
//         • 由colSize个SRAM存储器阵列组成
//         • 每个存储器单元的位宽为outputBufferDataWidth（32bit），长度为outputSramLength/jointSramLength
//         • 这些SRAM单元共享地址映射，使得一个地址对应colSize个字
//       • 二者不同之处：
//         • outputSram存储结果图Block（结果图的第0~groupNum行）
//         • jointSram缓存：
//           • k>0: 结果图Block的高向冗余（结果图的第groupNum+1~groupNum+k行）
//           • k=0: None
//   • 对于一个从Cluster到来的结果(坐标信息由（featureMapLine, count, cout, kernelRow）来定义，用于计算当前数据在输出缓存中的写位置）
//     • outputSram
//       • outputBaseAddr = (io.outputNoc.bits.cout * (groupNum + 1)) << 1
//       • outputWriteAddr = outputBaseAddr + ((k - io.outputNoc.bits.kernelRow) << 1) + (io.outputNoc.bits.featureMapLine << 1) + io.outputNoc.bits.count
//       • outputWriteEn = outputNoc.valid && (position <= groupNum)，其中position = featureMapLine + (k - kernelRow)
//     • jointSram
//       • jointBaseAddr = resolutionColIdx * (cout+1) * k + io.outputNoc.bits.cout * k
//       • jointWriteAddr = jointBaseAddr + (position-groupNum-1) + Mux(count === 0, 0, jointBufferBias)
//       • jointWriteEn = outputNoc.valid && (position > groupNum)
//       • jointBufferBias = (maxResolutionCol/colSize + 1) * (cout + 1) * k
//   • 根据这一位置，计算outputSram中对应可补齐/拼接数据的读位置，读位置及写行为的差异是输入通道补齐和列向拼接两种操作的核心差异：
//     • 初始列向拼接中，不需要拼接
//       • outputNoc上数据存储于outputSram或jointSram中
//     • 一般列向拼接中，需要拼接
//       • 若position < k（高向拼接）：
//         • jointSram的读地址jointHeightReadAddr = jointBaseAddr + position + Mux(count === 0, 0, jointBufferBias)
//         • 从jointSram的读地址读出数据后，与当前outputNoC上数据相加
//         • 将累加结果写入到outputSram(outputWriteAddr)中
//       • 若position > groupNum && count === 0（列向拼接）：
//         • 计算读使能与读地址
//           • outputReadAddr = outputWriteAddr + 1  
//           • jointWidthReadAddr = jointBaseAddr + position + jointBufferBias
//           • outputReadEn = workMode === 2 && position <= groupNum && count === 0 && outputWriteEn
//           • jointWidthReadEn = workMode === 2 && position > groupNum && count === 0
//         • 将读出的数据与outputNoc上数据累加
//         • 写回到outputSram或jointSram中（同outputWriteEn以及jointWriteEn判断逻辑）
//       • 若count=1
//           • outputNoc上数据存储outputSram或jointSram中
//     • 输入通道补齐模式中，可补齐数据的读位置与补齐后数据的写位置相同，即根据io.outputNoc.bits.featureMapLine的不同，从outputSram或者jointSram中读出数据，累加后写回到对应的写入地址中
//   • 读出-补齐(拼接)累加-写入 三个操作可以流水线化
// • 工作步骤
//   • 基于流水线实现
//     • 在outputNoc有数据时，压入数据与坐标信息，并压入En（读、写）信号outputSram或者jointSram
//     • 随流水线运行，EN信号也逐级传递，并在读数据与写回阶段发挥作用
//     • 流水线始终运行，不需要Valid驱动，在outputNoc.valid无效时，En信号掩码归零即可
//     • 所有数据，不管需不需要拼接或补齐，均通过这个流水线
//   • 流水线级数组成
//     • Stage 0: 空流水级，规避行读与列读重叠的情况，缓存地址和控制信号
//     • Stage 1: 充当通道补齐/高拼接读取缓冲1clk，列拼接读请求发送
//     • Stage 2: 将通道补齐/高拼接的读取结果累加，并充当列拼接读取缓冲的1CLK
//     • Stage 3: 将列拼接的读取结果累加，并写回
//   • 各个级别具体行为
//     • preStae（地址计算与信号缓存）：
//       • 计算读写地址和使能信号
//     • Stage 0（地址计算与信号缓存）：
//       • 缓存outputNoc数据、地址和控制信号
//       • 使用RegNext实现流水线传递
//     • Stage 1（读取缓冲）：
//       • 缓存Stage 0的所有信号
//       • 为Stage 2的累加操作准备数据
//     • Stage 2（高向拼接累加）：
//       • 执行高向拼接的累加操作
//       • 将累加结果传递给Stage 3
//       • 缓存列拼接的读取使能信号
//     • Stage 3（列拼接累加与写回）：
//       • 执行列拼接的累加操作
//       • 将最终结果写回到outputSram或jointSram
//       • 完成整个流水线操作
//////////////////////////////////////////////////////////////////////////////
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-08-13 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
package FLOOD_Accelerator.machine

import chisel3._ 
import chisel3.util._
import FLOOD_Accelerator.core.Config
import FLOOD_Accelerator.tools.DynamicTruncateData
import FLOOD_Accelerator.sram.pingpongBuffer

class OutRouterPlanePost extends Module {
  // Inherit parameters from Config
  val colSize = Config.colSize
  val tileSize = Config.tileSize
  val outputWidth = Config.outputWidth
  val outputBufferTmpWidth = Config.outputBufferTmpWidth
  val outputBufferDataWidth = Config.outputBufferDataWidth
  val finalWidth = Config.finalWidth
  val configDataWidth = Config.configDataWidth
  val outputAddrWidth = log2Ceil(Config.outputSramLength)
  val jointAddrWidth = log2Ceil(Config.jointSramLength)

  // Configuration bit widths
  val kernelBlockKWidth = log2Ceil(Config.maxKernelBlockK)
  val kernelBlockCoutWidth = log2Ceil(Config.maxKernelBlockCout)
  val groupSizeWidth = log2Ceil(Config.maxGroupSize)
  val groupNumWidth = log2Ceil(Config.maxGroupNum)
  val cinIdxWidth = log2Ceil(Config.maxKernelBlockCin/Config.rowSize + 1)
  val colIdxWidth = log2Ceil(Config.maxResolutionCol/Config.colSize + 1)
  val workModeWidth = log2Ceil(Config.maxWorkMode)  // 工作模式位宽
  val strideWidth = kernelBlockKWidth // 仅在k=0时生效的stride字段位宽
  val featBlkWidWidth = log2Ceil(Config.maxFeatureBlockWidth) // featBlkWid位宽
  val pixelParaWidth = log2Ceil(Config.maxPixelParallel) // pixelPara位宽

  // IO definition
  val io = IO(new Bundle {
    // Inherited from OutRouter
    val pingpong = Input(Bool())
    // 新增计算模式控制信号（一轮计算内有效）
    val actionMode = new Bundle {
      val dataFlowMode = Input(Bool()) // false: FLOOD, true: NVDIA
      val isFinalCinIdx = Input(Bool())
      val bnEn = Input(Bool())
      val actEn = Input(Bool())
      val poolEn = Input(Bool())
    }
    // 配置总线
    val configBus = new Bundle {
      val data = Input(UInt(configDataWidth.W))
      val addr = Input(UInt(Config.configAddrWidth.W))
      val en = Input(Bool())
    }
    // 输出Noc接口
    val outputNoc = Flipped(Decoupled(new Bundle {
      val data = Vec(colSize, SInt((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W))
      val featureMapLine = UInt((2*log2Ceil(tileSize)).W)
      val count = UInt(8.W)
      val cout = UInt(pixelParaWidth.W)
      val kernelRow = UInt(kernelBlockKWidth.W)
      val remain = UInt(16.W)
    }))

    // 完成信号
    val done = Decoupled(Bool())
    // 错误信号
    val error = Output(Bool())
  
    // outputSram写接口
    val outputSramWrite = new Bundle {
      val enable = Output(Bool())
      val address = Output(UInt(outputAddrWidth.W))
      val data = Output(UInt((colSize * outputBufferTmpWidth).W))
    }
    // outputSram读接口
    val outputSramRead = new Bundle {
      val enable = Output(Bool())
      val address = Output(UInt(outputAddrWidth.W))
      val data = Input(UInt((colSize * outputBufferTmpWidth).W))
    }
    
    // val outputjointBias = Output(UInt(outputAddrWidth.W))

    // jointSram写接口
    val jointSramWrite = new Bundle {
      val enable = Output(Bool())
      val address = Output(UInt(jointAddrWidth.W))
      val data = Output(UInt((colSize * outputBufferTmpWidth).W))
    }
    // jointSram读接口
    val jointSramRead = new Bundle {
      val enable = Output(Bool())
      val address = Output(UInt(jointAddrWidth.W))
      val data = Input(UInt((colSize * outputBufferTmpWidth).W))
    }
  })

  // Configuration buffer with workMode support（增加默认初值）

  // 创建normal配置寄存器（Reg）: {remain, stride, cout, groupNum, groupSize, k}
  // 参考FSM进行调整
  private val defaultK = 2.U(kernelBlockKWidth.W)  // 默认k=3
  private val defaultGroupSize = 0.U(groupSizeWidth.W)  // 默认groupSize=1
  private val defaultGroupNum = (Config.tileSize-1).U(groupNumWidth.W)  // 默认groupNum=tileSize
  private val defaultCout = 15.U(kernelBlockCoutWidth.W)  // 默认cout=16
  private val defaultStride = 0.U(strideWidth.W)
  private val normalUsedWidth = kernelBlockKWidth + groupSizeWidth + groupNumWidth + pixelParaWidth + strideWidth
  private val normalRemainWidth = configDataWidth - normalUsedWidth
  private val defaultNormalPacked = Cat(
    0.U(normalRemainWidth.W),
    defaultStride,
    defaultCout,
    defaultGroupNum,
    defaultGroupSize,
    defaultK
  )
  val configRegNormal = RegInit(defaultNormalPacked)
  when(io.configBus.en && (io.configBus.addr === Config.FSMRouterConfIdStart.U)) {
    configRegNormal := io.configBus.data
  }

  // 从Normal配置寄存器中获取k、groupSize、groupNum、cout、stride
  val k = configRegNormal(kernelBlockKWidth-1, 0) // 卷积核尺寸
  val groupSize = configRegNormal(kernelBlockKWidth + groupSizeWidth - 1, kernelBlockKWidth) // Cluster内每个Tile组内的Tile数量
  val groupNum = configRegNormal(kernelBlockKWidth + groupSizeWidth + groupNumWidth - 1, kernelBlockKWidth + groupSizeWidth) // 组数
  val cout = configRegNormal(kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCoutWidth - 1, kernelBlockKWidth + groupSizeWidth + groupNumWidth) // 输出通道数
  val stride = configRegNormal(kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCoutWidth + strideWidth - 1,
                               kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCoutWidth)

  // 创建Special配置寄存器（Reg）: {remain, truncateEn, truncateBits, workMode, colIdx, cinIdx}
  // 参考FSM进行Special配置寄存器定义
  private val truncateBitsWidth = log2Ceil(outputBufferTmpWidth)
  private val defaultCinIdx = 0.U(cinIdxWidth.W) // 默认cinIdx=0
  private val defaultColIdx = 0.U(colIdxWidth.W) // 默认colIdx=0
  private val defaultWorkMode = 0.U(workModeWidth.W) // 默认workMode=0
  private val defaultTruncateBits = 0.U(truncateBitsWidth.W) // 默认truncateBits=0
  private val defaultTruncateEn = 0.U(1.W) // 截位使能默认0
  private val specialUsedWidth = cinIdxWidth + colIdxWidth + workModeWidth + truncateBitsWidth + 1
  private val specialRemainWidth = configDataWidth - specialUsedWidth
  private val defaultSpecialPacked = Cat(
    0.U(specialRemainWidth.W),
    defaultTruncateEn,
    defaultTruncateBits,
    defaultWorkMode,
    defaultColIdx,
    defaultCinIdx
  )
  val configRegSpecial = RegInit(defaultSpecialPacked)
  when(io.configBus.en && (io.configBus.addr === Config.FSMRouterConfIdEnd.U)) {
    configRegSpecial := io.configBus.data
  }
  
  // 从寄存器中获取CinIdx等参数
  val cinIdx = configRegSpecial(cinIdxWidth - 1, 0) // 当前特征图Block的输入通道组序号
  val colIdx = configRegSpecial(cinIdxWidth + colIdxWidth - 1, cinIdxWidth) // 当前特征图Block的列向组序号
  val workMode = configRegSpecial(cinIdxWidth + colIdxWidth + workModeWidth - 1, cinIdxWidth + colIdxWidth) // 当前工作模式
  
  // 截位位数控制字段（新增）
  val truncateBits = configRegSpecial(cinIdxWidth + colIdxWidth + workModeWidth + truncateBitsWidth - 1, 
                                     cinIdxWidth + colIdxWidth + workModeWidth) // 截位位数，默认为0
  // 截位使能控制字段（新增）
  val truncateEn = configRegSpecial(cinIdxWidth + colIdxWidth + workModeWidth + truncateBitsWidth) // 单bit
  //Config寄存器位宽检查
  require(configDataWidth >= cinIdxWidth + colIdxWidth + workModeWidth + truncateBitsWidth + 1, "OutRouter中Special寄存器位宽不足")

  // ========================= NVDLA REG 配置寄存器 =========================
  // NVDLA REG: {remain, featBlkWid, ky, kx}
  private val defaultKx = 0.U(kernelBlockKWidth.W)  // 默认kx=0
  private val defaultKy = 0.U(kernelBlockKWidth.W)  // 默认ky=0
  private val defaultFeatBlkWid = 0.U(featBlkWidWidth.W)  // 默认featBlkWid=0
  private val nvdlaRegUsedWidth = kernelBlockKWidth + kernelBlockKWidth + featBlkWidWidth
  private val nvdlaRegRemainWidth = configDataWidth - nvdlaRegUsedWidth
  private val defaultNvdlaRegPacked = Cat(
    0.U(nvdlaRegRemainWidth.W),
    defaultFeatBlkWid,
    defaultKy,
    defaultKx
  )
  val configRegNvdla = RegInit(defaultNvdlaRegPacked)
  when(io.configBus.en && (io.configBus.addr === Config.nvdlaRegId.U)) {
    configRegNvdla := io.configBus.data
  }
  
  // 从NVDLA REG配置寄存器中获取kx、ky、featBlkWid参数
  val kx = configRegNvdla(kernelBlockKWidth - 1, 0) // 当前像素位置kx
  val ky = configRegNvdla(kernelBlockKWidth + kernelBlockKWidth - 1, kernelBlockKWidth) // 当前像素位置ky
  val featBlkWid = configRegNvdla(kernelBlockKWidth + kernelBlockKWidth + featBlkWidWidth - 1, kernelBlockKWidth + kernelBlockKWidth) // 特征图块宽度
  val pixelPara = configRegNvdla(kernelBlockKWidth + kernelBlockKWidth + featBlkWidWidth + pixelParaWidth - 1, kernelBlockKWidth + kernelBlockKWidth + featBlkWidWidth) // 像素并行参数

  // ========================= BN 参数寄存器（colSize 个）=========================
  // tileId 分配：2*tileSize 到 2*tileSize + colSize - 1
  val bnMulParams = Wire(Vec(colSize, SInt(outputBufferDataWidth.W)))
  val bnAddParams = Wire(Vec(colSize, SInt(outputBufferDataWidth.W)))
  for (i <- 0 until colSize) {
    val bnReg = RegInit(0.U(configDataWidth.W))
    when(io.configBus.en && (io.configBus.addr === (Config.bnConfIdStart + i).U)) {
      bnReg := io.configBus.data
    }
    // 约定：低 outputBufferDataWidth 位为 BN 加法参数，加法为有符号；
    //      其上的 outputBufferDataWidth 位为 BN 乘法参数，乘法为有符号；
    bnAddParams(i) := bnReg(outputBufferDataWidth-1, 0).asSInt
    bnMulParams(i) := bnReg(2*outputBufferDataWidth-1, outputBufferDataWidth).asSInt
  }

  // 根据数据流模式选择参数：
  // FLOOD（false）：使用 index 0 的参数应用到所有列；
  // NVDIA（true）：为每列使用对应的参数；
  def getBnMulParam(index: Int): SInt = Mux(io.actionMode.dataFlowMode, bnMulParams(index), bnMulParams(0))
  def getBnAddParam(index: Int): SInt = Mux(io.actionMode.dataFlowMode, bnAddParams(index), bnAddParams(0))

  // Data truncation function with quantization support
  // 自动识别vec内元素位宽，并根据与outWidth的关系进行不同处理
  // SINT数据截位，支持量化截位和四舍五入
  def truncateData(dataVec: Vec[SInt], outWidth: Int, truncateBits: Int = 0): Vec[SInt] = {
    val elemWidth = dataVec(0).getWidth
    val truncateData = Wire(Vec(colSize, SInt(outWidth.W)))
    
    // 根据位宽关系自动决定电路结构
    if (elemWidth > outWidth) {
      // 饱和截位：当数据超过上限时，取到上限值
      val maxValue = (1 << (outWidth - 1)) - 1  // 正数最大值
      val minValue = -(1 << (outWidth - 1))     // 负数最小值
      
      for (i <- 0 until colSize) {
        val data = dataVec(i)
        
        // 应用量化截位和四舍五入
        val quantizedData = if (truncateBits > 0) {
          // 量化截位：去除低truncateBits个bit
          val shiftedData = data >> truncateBits
          
          // 四舍五入：检查被截去的最高位
          val roundBit = data.asUInt()(truncateBits - 1)
          val stickyBits = if (truncateBits > 1) data.asUInt()(truncateBits - 2, 0).orR() else false.B
          val shouldRound = roundBit && (shiftedData(0) || stickyBits)
          
          Mux(shouldRound, shiftedData + 1.S, shiftedData)
        } else {
          data
        }
        
        val truncated = quantizedData.asUInt()(outWidth-1, 0).asSInt
        
        // 检查是否发生溢出
        val isOverflow = quantizedData > maxValue.S || quantizedData < minValue.S
        
        // 饱和截位：溢出时取边界值，否则取截断值
        truncateData(i) := Mux(isOverflow, 
          Mux(quantizedData > 0.S, maxValue.S, minValue.S),  // 溢出时根据符号选择边界
          truncated                                           // 未溢出时取截断值
        )
      }
    } else if (elemWidth == outWidth) {
      // 直接赋值，不需应用量化截位
      for (i <- 0 until colSize) {
        truncateData(i) := dataVec(i)
      }
    } else {
      // 位宽不足，补符号位
      for (i <- 0 until colSize) {
        val signBit = dataVec(i).asUInt()(elemWidth-1)
        truncateData(i) := Cat(Fill(outWidth-elemWidth, signBit), dataVec(i).asUInt()).asSInt
      }
    }
    truncateData
  }

  // Pipeline stage prepare: Address calculation
  // Base address calculations
  val outputBaseAddr = (io.outputNoc.bits.cout * (groupNum +& 1.U))
  val jointBaseAddr = colIdx * (cout +& 1.U) * k + io.outputNoc.bits.cout * k // 每次写入的基地址
  val jointBufferBias = (Config.maxResolutionCol/Config.colSize + 1).U * (cout +& 1.U) * k // 拼接缓存区的基地址偏移量
  val outputBufferBias = (Config.maxKernelBlockCout * Config.maxGroupNum).U // 输出缓存区的基地址偏移量(存储count=1的数据)
  // io.outputjointBias := outputBufferBias
  // Write enable conditions
  val position = Mux(io.outputNoc.valid, io.outputNoc.bits.featureMapLine + (k - io.outputNoc.bits.kernelRow), 0.U)
  
  val outputWriteEn = io.outputNoc.valid && 
                     (position <= groupNum) 
                     
  val jointWriteEn = io.outputNoc.valid && 
                    (position > groupNum) 

  // Write address calculations
  val outputWriteAddr = Mux(outputWriteEn, outputBaseAddr +& position +& 
                       Mux(io.outputNoc.bits.count === 0.U, 0.U, outputBufferBias), 0.U) // 如果count=1，则加上偏移
  val jointWriteAddr = Mux(jointWriteEn, jointBaseAddr + (position-groupNum-1.U) + 
                        Mux(io.outputNoc.bits.count === 0.U, 0.U, jointBufferBias), 0.U) // 如果count=1，则加上偏移

  // Read address and enable calculations
  // 需要读取数据的情况
  // 最左上角：workMode === 0.U
  // 初始列向拼接：workMode === 1.U
  // 一般列向拼接：workMode === 2.U
  // 仅输入通道补齐：workMode === 3.U
  // 列向拼接：workMode === 4.U

  // 标志信号
  val groupNumLowerThanK = groupNum < k
  val positionLEThanGroupnum = position <= groupNum
  val needRead = workMode === 1.U || workMode === 2.U || workMode === 3.U || workMode === 4.U
  
  // 读地址计算
  val outputReadAddr = Mux(workMode === 3.U, outputWriteAddr, // cin补齐
                         Mux((workMode === 4.U || workMode === 2.U) && positionLEThanGroupnum && io.outputNoc.bits.count === 0.U, // 列向拼接
                             outputWriteAddr + outputBufferBias, 0.U))

  // 拼接缓存读地址计算
  // 高向拼接
  val jointHeightReadAddr = Mux(workMode === 3.U, jointWriteAddr, // 通道补齐
                          Mux((workMode === 2.U || workMode === 1.U) && position < k, // 高向拼接（joint结果区，拼接缓存区都要更新）
                              jointBaseAddr + position + Mux(io.outputNoc.bits.count === 0.U, 0.U, jointBufferBias), (1<<jointAddrWidth-1).U))
  // 列向拼接
  val jointWidthReadAddr = Mux((workMode ===4.U || workMode === 2.U) && position > groupNum && io.outputNoc.bits.count === 0.U, // 列向拼接（只有预期写入joint结果区内的数据要拼接读取）
                            (jointBaseAddr + (position-groupNum-1.U) + jointBufferBias - (cout +& 1.U)*k), 0.U)


  val outputReadEn = needRead && io.outputNoc.valid &&
                    (workMode === 3.U && outputWriteEn || 
                     (workMode === 4.U || workMode === 2.U) && position <= groupNum && io.outputNoc.bits.count === 0.U && outputWriteEn)
                   
  val jointHeightReadEn = needRead && io.outputNoc.valid && // 高向拼接或通道补齐读使能（S1）
                   (workMode === 3.U && position > groupNum || // 通道补齐（对两个count都有效）
                    (workMode === 2.U || workMode === 1.U) && position < k && !groupNumLowerThanK && io.outputNoc.bits.count === 0.U ||  // 高向拼接（groupNum >= k 的情况），仅count=0时有效
                    (workMode === 2.U || workMode === 1.U) && position < k && groupNumLowerThanK && io.outputNoc.bits.count === 0.U) // 高向拼接（groupNum < k 的情况），仅count=0时有效
  
  val jointWidthReadEn = needRead && io.outputNoc.valid && // 列向拼接读使能(S2)
                    ((workMode === 4.U || workMode === 2.U) && position > groupNum && io.outputNoc.bits.count === 0.U) // 列向拼接，仅count=0时有效

  // pipeline stage 0: 空流水级，规避行读与列读重叠的情况
  val s0_truncatedData = truncateData(io.outputNoc.bits.data, Config.outputBufferTmpWidth, truncateBits=0) // 将outputNoc数据高位截断为outputBufferTmpWidth bits（量化） 
  val s0_valid = RegNext(io.outputNoc.valid, false.B)
  val s0_count = RegNext(io.outputNoc.bits.count)
  val s0_position = RegNext(position)
  val s0_cout = RegNext(io.outputNoc.bits.cout)
  val s0_currentData = RegNext(s0_truncatedData)
  val s0_outputWriteAddr = RegNext(outputWriteAddr)
  val s0_outputWriteEn = RegNext(outputWriteEn)
  val s0_jointWriteAddr = RegNext(jointWriteAddr)
  val s0_jointWriteEn = RegNext(jointWriteEn)
  // 在 outputNoc.valid 时形成的偏移标志（只对输出写路径有效，且 count==1 才加偏移）
  val s0_outputWriteBiasApplied = RegNext(io.outputNoc.valid && outputWriteEn && (io.outputNoc.bits.count === 1.U), false.B)
  val s0_workMode = RegNext(workMode)
  val s0_outputReadEn = RegNext(outputReadEn)
  val s0_jointHeightReadEn = RegNext(jointHeightReadEn)
  val s0_jointHeightReadAddr = RegNext(jointHeightReadAddr)
  val s0_jointWidthReadEn = RegNext(jointWidthReadEn)
  val s0_jointWidthReadAddr = RegNext(jointWidthReadAddr)

  // Pipeline stage 1: 充当通道补齐/高拼接/position<=groupNum时的列拼接  三种读取行为的读取缓冲(1clk)，列拼接读请求发送，同时完成通道补齐/高拼接的读取结果累加
  val s1_valid = RegNext(s0_valid, false.B)
  val s1_count = RegNext(s0_count)
  val s1_position = RegNext(s0_position)
  val s1_cout = RegNext(s0_cout)
  val s1_currentData = RegNext(s0_currentData)
  val s1_outputWriteAddr = RegNext(s0_outputWriteAddr)
  val s1_outputWriteEn = RegNext(s0_outputWriteEn)
  val s1_jointWriteAddr = RegNext(s0_jointWriteAddr)
  val s1_jointWriteEn = RegNext(s0_jointWriteEn)
  val s1_outputWriteBiasApplied = RegNext(s0_outputWriteBiasApplied, false.B)
  val s1_workMode = RegNext(s0_workMode)
  val s1_outputReadEn = RegNext(s0_outputReadEn)
  val s1_jointHeightReadEn = RegNext(s0_jointHeightReadEn) 
  val s1_jointWidthReadEn = RegNext(s0_jointWidthReadEn)
  val s1_jointWidthReadAddr = RegNext(s0_jointWidthReadAddr)

  // 通道补齐/高拼接的读取结果累加
  // Helpers to unpack bus to Vec - 自动识别位宽
  def unpackBusToVec(bus: UInt, targetElemWidth: Int): Vec[UInt] = {
    val busElemWidth = bus.getWidth / colSize
    require(bus.getWidth >= colSize * targetElemWidth, s"Bus width (${bus.getWidth}) must be >= colSize * targetElemWidth (${colSize * targetElemWidth})")
    require(busElemWidth >= targetElemWidth, s"Bus element width (${busElemWidth}) must be >= target element width (${targetElemWidth})")
    
    val vec = Wire(Vec(colSize, UInt(targetElemWidth.W)))
    for (i <- 0 until colSize) {
      // 从bus中提取每个元素，然后截断到目标位宽
      val busElement = bus((i+1)*busElemWidth-1, i*busElemWidth)
      vec(i) := busElement(targetElemWidth-1, 0)
    }
    vec
  }
  val zeroVec = VecInit(Seq.fill(colSize)(0.U(outputBufferTmpWidth.W)))
  // Select which read data to use
  val s1_jointReadData = Mux(s1_jointHeightReadEn, unpackBusToVec(io.jointSramRead.data, outputBufferTmpWidth), zeroVec)
  val s1_outputReadData = Mux(s1_outputReadEn, unpackBusToVec(io.outputSramRead.data, outputBufferTmpWidth), zeroVec)
  
  // Element-wise addition for vector data
  val s1_mergedData = Wire(Vec(colSize, SInt((outputBufferTmpWidth).W))) // 预留加法进位
  
  // Element-wise addition with conditional selection
  for (i <- 0 until colSize) {
    s1_mergedData(i) := s1_currentData(i) +& s1_jointReadData(i).asSInt +& s1_outputReadData(i).asSInt
  }

  // Pipeline stage 2: 将position>groupNum时的列拼接的读取结果累加，并写回
  val s2_valid = RegNext(s1_valid, false.B)
  val s2_count = RegNext(s1_count)
  val s2_position = RegNext(s1_position)
  val s2_cout = RegNext(s1_cout)
  val s2_currentData = RegNext(s1_mergedData)
  val s2_outputWriteAddr = RegNext(s1_outputWriteAddr)
  val s2_outputWriteEn = RegNext(s1_outputWriteEn)
  val s2_jointWriteAddr = RegNext(s1_jointWriteAddr)
  val s2_jointWriteEn = RegNext(s1_jointWriteEn)
  val s2_outputWriteBiasApplied = RegNext(s1_outputWriteBiasApplied, false.B)
  val s2_workMode = RegNext(s1_workMode)
  val s2_jointWidthReadEn = RegNext(s1_jointWidthReadEn)

  // Select which read data to use
  val s2_jointReadData = Mux(s2_jointWidthReadEn, unpackBusToVec(io.jointSramRead.data, outputBufferTmpWidth), zeroVec)
  
  // Element-wise addition for vector data
  val s2_mergedData = Wire(Vec(colSize, SInt((outputBufferTmpWidth).W)))
  
  // Element-wise addition with conditional selection
  for (i <- 0 until colSize) {
    s2_mergedData(i) := s2_currentData(i) +& s2_jointReadData(i).asSInt
  }

  // ========================= 新流水线：BNM -> ActA -> MaxPool =========================
  // 条件：当 isFinalCinIdx 无效时，跳过全部新增流水级，直接写回
  val finalCinValid = Wire(Bool())
  finalCinValid := io.actionMode.isFinalCinIdx
  // 数据流为NVDLA时，poolEn无效
  // val poolEn = io.actionMode.poolEn && io.actionMode.dataFlowMode === 0.U
  // 只有 count==0 的数据，才能进入后级流水

  // ------- BNM 阶段（乘法，条件执行） -------
  // 引入BN折叠后，去除BNM流水级
  // // 插入寄存：S2 -> BNM 输入
  // val bnm_valid = RegNext(s2_valid && finalCinValid, false.B)
  // val s2_toBnmData = Wire(Vec(colSize, SInt((s2_mergedData(0).getWidth).W)))
  // for (i <- 0 until colSize) { // 当finalCinValid有效时，传递s2_mergedData，否则传递0
  //   s2_toBnmData(i) := Mux(finalCinValid, s2_mergedData(i), 0.S)
  // }
  // val bnm_currentData = RegNext(s2_toBnmData)
  // val bnm_outputWriteEn = RegNext(s2_outputWriteEn && finalCinValid, false.B)
  // val bnm_jointWriteEn  = RegNext(s2_jointWriteEn && finalCinValid, false.B)
  // val bnm_outputAddr = RegNext(s2_outputWriteAddr)
  // val bnm_jointAddr  = RegNext(s2_jointWriteAddr)
  // val bnm_mergedData = Wire(Vec(colSize, SInt((s2_mergedData(0).getWidth+getBnMulParam(0).getWidth).W)))
  // // BNM 对 joint 路径不生效；对 output 路径不限
  // val bnm_apply = io.actionMode.bnEn && (bnm_outputWriteEn))
  
  // when(finalCinValid) { // 在finalCinValid有效时，才可能会执行bnm流水级,从而在其无效时关闭乘法器
  //   when(bnm_apply) { // 在bnm_apply有效时，才可能会执行bnm流水级,从而在其无效时关闭乘法器
  //     for (i <- 0 until colSize) {
  //       val src = bnm_currentData(i)
  //       val mulParam = getBnMulParam(i).asSInt
  //       val mulRes = (src * mulParam).asSInt
  //       bnm_mergedData(i) := mulRes
  //     }
  //   }.otherwise { // 在bnm_apply无效时，继承bnm_currentData
  //     for (i <- 0 until colSize) {
  //       bnm_mergedData(i) := bnm_currentData(i)
  //     }
  //   }
  // }.otherwise {
  //   for (i <- 0 until colSize) {
  //     bnm_mergedData(i) := 0.S
  //   }
  // }

  // ------- ActA 阶段（加法 + ReLU，条件执行） -------
  // val act_valid = RegNext(bnm_valid, false.B)
  // val act_currentData = RegNext(bnm_mergedData)
  // val act_outputWriteEn = RegNext(bnm_outputWriteEn, false.B)
  // val act_jointWriteEn  = RegNext(bnm_jointWriteEn, false.B)
  // val act_outputAddr = RegNext(bnm_outputAddr)
  // val act_jointAddr  = RegNext(bnm_jointAddr)
  // val act_mergedData = Wire(Vec(colSize, SInt((s2_mergedData(0).getWidth+getBnMulParam(0).getWidth+getBnAddParam(0).getWidth).W)))
  
  // val act_applyAdd  = io.actionMode.bnEn  && (act_outputWriteEn))
  // val act_applyRelu = io.actionMode.actEn && (act_outputWriteEn))
  val act_valid = RegNext(s2_valid && finalCinValid, false.B)
  // debug: 检查s2_count的有效性，避免宽度不匹配或信号异常
  val act_count = RegNext(Mux(finalCinValid, s2_count, 0.U(8.W)))
  val act_cout = RegNext(Mux(finalCinValid, s2_cout, 0.U(8.W)))
  val act_position = RegNext(Mux(finalCinValid, s2_position, 0.U(8.W)))
  // 偏移标志在act阶段的对齐
  val act_outputWriteBiasApplied = RegNext(Mux(finalCinValid, s2_outputWriteBiasApplied, false.B), false.B)
  
  val s2_toActAData = Wire(Vec(colSize, SInt((s2_mergedData(0).getWidth).W)))
  for (i <- 0 until colSize) { // 当finalCinValid有效时，传递s2_mergedData，否则传递0
    s2_toActAData(i) := Mux(finalCinValid, s2_mergedData(i), 0.S)
  }

  // ！！！！低位截位！！！！ - 使用DynamicTruncateData模块
  val s2_truncateModule = Module(new DynamicTruncateData(
    inputWidth = s2_mergedData(0).getWidth,
    outputWidth = outputBufferDataWidth,  // 有效位宽
    vecSize = colSize,
    truncateBitsWidth = truncateBitsWidth
  ))
  
  // 连接截位模块
  s2_truncateModule.io.inputData := s2_mergedData
  s2_truncateModule.io.truncateBits := truncateBits
  s2_truncateModule.io.en := truncateEn
  
  val s2_toActDataTruncated = Mux(s2_count === 0.U && s2_outputWriteEn, 
    s2_truncateModule.io.outputData, // count==0时，对outputWriteEn有效时，使用DynamicTruncateData截断（输出位宽与输入一致，只有低outputBufferTmpWidth位有效）
    s2_mergedData) // count==1或outputWriteEn无效时，不截断，s2_mergedData已经是outputBufferTmpWidth精度,直接使用
  val act_currentData = RegNext(s2_toActDataTruncated)
  val act_outputWriteEn = RegNext(Mux(finalCinValid, s2_outputWriteEn, false.B))
  val act_jointWriteEn  = RegNext(Mux(finalCinValid, s2_jointWriteEn, false.B))
  val act_outputAddr = RegNext(s2_outputWriteAddr, 0.U(outputAddrWidth.W))
  val act_jointAddr  = RegNext(s2_jointWriteAddr, 0.U(jointAddrWidth.W))
  val act_mergedData = Wire(Vec(colSize, SInt((s2_currentData(0).getWidth+1).W)))
  // ActA 对累加的执行判定
  val act_applyAdd  = io.actionMode.bnEn  && (act_outputWriteEn)
  val act_applyRelu = io.actionMode.actEn && (act_outputWriteEn)
  // ActA 对 ReLU 的执行判定
  when(finalCinValid) {
    when(act_count === 0.U && (act_applyAdd || act_applyRelu)) { // 在count==0且act_applyAdd或act_applyRelu有效时，才可能会执行act流水级,从而在其无效时关闭加法器和ReLU
      for (i <- 0 until colSize) {
        val addParam = getBnAddParam(i)
        val preAdd = act_currentData(i)
        val afterAdd = Mux(act_applyAdd, (preAdd +& addParam).asSInt, preAdd)
        val afterRelu = Mux(act_applyRelu && afterAdd.head(1).asBool, 0.S(afterAdd.getWidth.W), afterAdd)
        act_mergedData(i) := afterRelu
      }
    }.otherwise { // 在s2_count===0或（act_applyAdd、act_applyRelu均无效时），继承act_currentData
      for (i <- 0 until colSize) {
        act_mergedData(i) := act_currentData(i)
      }
    }
  }.otherwise {
    for (i <- 0 until colSize) {
      act_mergedData(i) := 0.S
    }
  }

  // ------- MaxPool 两级流水（PoolF / PoolS） -------
  // PoolF：对 ActA 输出做 pairwise max 生成 half，并寄存相关控制
  val poolF_valid = RegNext(act_valid, false.B)
  val poolF_count = RegNext(act_count)
  val poolF_position = RegNext(act_position)
  val poolF_cout = RegNext(act_cout)
  // 偏移标志在poolF阶段的对齐
  val poolF_outputWriteBiasApplied = RegNext(act_outputWriteBiasApplied, false.B)
  
  // 将act_mergedData截断为outputBufferDataWidth后，再进行比较 - 根据count条件分支处理
  val act_toPoolFDataTruncated = truncateData(act_mergedData, Config.outputBufferTmpWidth, truncateBits=0) // 低位截位到outputBufferTmpWidth
  val poolF_currentData = RegNext(act_toPoolFDataTruncated)
  val poolF_outputWriteEn = RegNext(act_outputWriteEn, false.B)
  val poolF_jointWriteEn  = RegNext(act_jointWriteEn, false.B)
  val poolF_outputAddr = RegNext(act_outputAddr)
  val poolF_jointAddr  = RegNext(act_jointAddr)
  // 要执行pool运算的标志信号：Pool 对 joint 路径不生效；对 output 路径始终生效。对所有数据，都仅在poolEn有效且count==0时，才执行pool运算
  val poolF_apply = io.actionMode.poolEn && (poolF_count === 0.U) && (poolF_outputWriteEn)
  val poolF_vec = Wire(Vec(colSize, SInt(poolF_currentData(0).getWidth.W)))
  for (i <- 0 until colSize) {
    poolF_vec(i) := Mux(finalCinValid, poolF_currentData(i), 0.S)
  }

  // 新增：行计数器，判断是否为第0/2/4...次输入
  // val pool_rowCounter = RegInit(0.U(1.W)) // 假设最大行数不会超过255，可根据实际需求调整位宽
  // val pool_rowCounterNext = pool_rowCounter + 1.U
  // when(poolF_valid && poolF_count === 1.U) { // 在poolF_apply有效且count==1时（适配flood模式），才可能执行行计数器
  //   pool_rowCounter := pool_rowCounterNext
  // }
  // val poolF_isEvenRow = pool_rowCounterNext(0) === 0.U // 低位为0表示偶数行（第0/2/4...次输入）
  val poolF_isEvenRow = poolF_position(0) === 0.U

  when(finalCinValid) {
    for (i <- 0 until colSize/2) {
      val a = poolF_currentData(2*i)
      val b = poolF_currentData(2*i+1)
      when(poolF_apply) { // 在poolF_apply有效时，执行pool一行每两个元素比较行为
        poolF_vec(i) := Mux(a >= b, a, b)
        poolF_vec(i+colSize/2) := 0.S
      }.otherwise { // 在poolF_apply无效时，直接传递
        poolF_vec(2*i) := a
        poolF_vec(2*i+1) := b
      }
    }
  }.otherwise {
    for (i <- 0 until colSize) {
      poolF_vec(i) := 0.S
    }
  }

  // PoolS：这里将pool次输出；将poolS_data与poolF_data进行逐元素大小比较，得到最终的maxpool结构（s=2）
  val poolS_valid = RegNext(poolF_valid, false.B)
  val poolS_count = RegNext(poolF_count)
  val poolS_position = RegNext(poolF_position)
  val poolS_cout = RegNext(poolF_cout)
  // 偏移标志在poolS阶段的对齐
  val poolS_outputWriteBiasApplied = RegNext(poolF_outputWriteBiasApplied, false.B)
  //数据准备
  val poolS_isEvenRow = poolS_position(0) === 0.U
  // 在第二拍视角下，两个行向量的下方行
  val poolF_data = RegNext(poolF_vec)
  
  // 创建tileSize/2个pools_data以及相应的compare Flag
  val poolsDataSize = tileSize / 2
  val pools_datas = RegInit(VecInit(Seq.fill(poolsDataSize)(VecInit(Seq.fill(colSize)(0.S(poolF_data(0).getWidth.W))))))
  val compFlags = RegInit(VecInit(Seq.fill(poolsDataSize)(false.B)))
  
  // 计算当前数据对应的pools索引
  val poolsIndex = poolS_position >> 1  // poolF_position / 2
  
  val pool_mergedData = Wire(Vec(colSize, SInt(poolF_data(0).getWidth.W))) // 初始化最终的pool后向量结果maxpool_vec
  val poolS_outputWriteEn = RegNext(poolF_outputWriteEn, false.B)// 在执行pool情况下，每两个行向量的地址间隔为2
  val poolS_jointWriteEn  = RegNext(poolF_jointWriteEn, false.B)
  val poolS_outputAddr = RegNext(poolF_outputAddr)
  val pool_outputAddr = Wire(UInt(outputAddrWidth.W)) // 在pool_processValid或pool_passValid有效时，才可能执行写回行为
  pool_outputAddr := poolS_outputAddr
  val poolS_jointAddr  = RegNext(poolF_jointAddr)
  val pool_jointAddr = Wire(UInt(jointAddrWidth.W)) // 在pool_processValid或pool_passValid有效时，才可能执行写回行为
  pool_jointAddr := poolS_jointAddr

  // PoolS_apply 有效(要执行maxpool行为)条件：PoolEn 有效且（outputSram写入或jointSram写入但isbottom) 且为偶数行。对所有数据，都仅在poolEn有效且count==0时，才执行pool运算
  val poolS_apply = io.actionMode.poolEn && (poolF_count === 0.U) && poolF_outputWriteEn
  
  // 当poolS_apply有效时，执行pool操作
  val pool_processEn = poolF_valid && poolS_apply
  val pool_passEn = poolF_valid && !poolS_apply
  val pool_processValid = RegNext(pool_processEn, false.B)
  val pool_passValid = RegNext(pool_passEn, false.B)
  
  // 根据compFlag状态决定行为
  val currentCompFlag = compFlags(poolsIndex)
  val pool_writeValid = Wire(Bool())

  when(finalCinValid) { // 在finalCinValid有效时，才可能会执行poolS流水级,从而在其无效时关闭比较器
    when(pool_processValid) { // 执行pool两个行逐元素比较行为的判断信号
      when(!currentCompFlag) { // compFlag=0: 将poolFData的数据写入对应位置的poolsdata
        // 写入pools_datas
        pools_datas(poolsIndex) := poolF_data
        compFlags(poolsIndex) := true.B
        
        // 不输出数据，仅存储
        pool_writeValid := false.B
        pool_outputAddr := poolS_outputAddr
        for (j <- 0 until colSize) {
          pool_mergedData(j) := 0.S
        }
      }.otherwise { // compFlag=1: 将poolFData与相应的pools_data比较，将更大的数输出
        // 执行逐元素比较
        for (j <- 0 until colSize/2) {
          val a = poolF_data(j)
          val b = pools_datas(poolsIndex)(j)
          pool_mergedData(j) := Mux(a >= b, a, b)
        }
        
        // 将下半部分清零
        for (j <- 0 until colSize/2) {
          pool_mergedData(j+colSize/2) := 0.S
        }
        
        // 输出比较结果
        pool_writeValid := true.B
        pool_outputAddr := Mux(poolS_position(0)===0.U, poolS_outputAddr+1.U, poolS_outputAddr)
        
        // 重置compFlag
        compFlags(poolsIndex) := false.B
      }
    }.elsewhen(pool_passValid) { // 不需要执行pool两行逐元素比较的情况
      pool_outputAddr := poolS_outputAddr
      pool_writeValid := true.B
      for (j <- 0 until colSize) {
        pool_mergedData(j) := poolF_data(j) // 直接传输数据
      }
    }.otherwise { // poolF没有数据或者poolS_apply无效且poolF有数据时，直接传递数据但不写回
      for (j <- 0 until colSize) {
        pool_mergedData(j) := poolF_data(j)
      }
      pool_outputAddr := poolS_outputAddr
      pool_writeValid := false.B
    }
  }.otherwise { // 在finalCinValid无效时，直接置零
    for (j <- 0 until colSize) {
      pool_mergedData(j) := 0.S
    }
    pool_outputAddr := poolS_outputAddr
    pool_writeValid := false.B
  }

  // Read from SRAMs
  // 在outputValid后通道补齐/高拼接立即发出读请求
  io.outputSramRead.enable := io.outputNoc.valid && outputReadEn
  io.outputSramRead.address := outputReadAddr
  io.jointSramRead.enable := (io.outputNoc.valid && jointHeightReadEn) || (s0_valid && s0_jointWidthReadEn)
  io.jointSramRead.address := Mux(s0_valid && s0_jointWidthReadEn, s0_jointWidthReadAddr, Mux(io.outputNoc.valid && jointHeightReadEn, jointHeightReadAddr, 0.U))

  // Write to SRAMs
  // pack Vec to bus - 自动识别位宽
  def packVecToBus(vec: Vec[UInt], targetBusWidth: Int): UInt = {
    val vecElemWidth = vec(0).getWidth
    val targetElemWidth = targetBusWidth / colSize
    require(targetBusWidth >= colSize * vecElemWidth, s"Target bus width (${targetBusWidth}) must be >= colSize * vecElemWidth (${colSize * vecElemWidth})")
    require(targetElemWidth >= vecElemWidth, s"Target element width (${targetElemWidth}) must be >= vec element width (${vecElemWidth})")
    
    val bus = Wire(UInt(targetBusWidth.W))
    var acc = 0.U(targetBusWidth.W)
    for (i <- 0 until colSize) {
      // 将vec元素扩展到目标位宽，然后打包到bus中
      val extendedElement = if (targetElemWidth > vecElemWidth) {
        Cat(0.U((targetElemWidth - vecElemWidth).W), vec(i))
      } else {
        vec(i)
      }
      acc = acc | (extendedElement << (i * targetElemWidth).U)
    }
    bus := acc
    bus
  }
  // =============== 最终写回选择 ===============
  // s2输出总线 - 根据count条件分支处理
  // // ！！！！低位截位！！！！ - 使用DynamicTruncateData模块
  // val s2_output_truncateModule = Module(new DynamicTruncateData(
  //   inputWidth = s2_mergedData(0).getWidth,
  //   outputWidth = Config.outputBufferDataWidth,  // 有效位宽
  //   vecSize = colSize,
  //   truncateBitsWidth = truncateBitsWidth
  // ))
  
  // // 连接截位模块
  // s2_output_truncateModule.io.inputData := s2_mergedData // 设定TmpWidth位宽覆盖了累加的位宽需求，不需要再做量化处理
  // s2_output_truncateModule.io.truncateBits := truncateBits
  
  val s2_mergedDataTruncated = s2_mergedData
  val s2_mergedDataTruncatedUInt = Wire(Vec(colSize, UInt(Config.outputBufferTmpWidth.W)))
  for (i <- 0 until colSize) {
    // 提取低outputBufferTmpWidth位作为有效位
    s2_mergedDataTruncatedUInt(i) := s2_mergedDataTruncated(i).asUInt(Config.outputBufferTmpWidth - 1, 0)
  }
  val s2_mergedDataBus = packVecToBus(s2_mergedDataTruncatedUInt, colSize * outputBufferTmpWidth)
  
  // 池化输出总线(pool_mergedData已经是截位后的数据，位宽为TmpWidth，直接打包)
  val pool_mergedDataTruncated = pool_mergedData
    
  val pool_mergedDataTruncatedUInt = Wire(Vec(colSize, UInt(Config.outputBufferTmpWidth.W)))
  for (i <- 0 until colSize) {
    pool_mergedDataTruncatedUInt(i) := pool_mergedDataTruncated(i).asUInt
  }
  val pool_mergedDataBus = packVecToBus(pool_mergedDataTruncatedUInt, colSize * outputBufferTmpWidth)

  // 写回仲裁：
  val final_outputEn = Wire(Bool())
  val final_outputAddr = Wire(UInt(outputAddrWidth.W))
  val final_outputData = Wire(UInt((colSize * outputBufferTmpWidth).W))
  val final_jointEn = Wire(Bool())
  val final_jointAddr = Wire(UInt(jointAddrWidth.W))
  val final_jointData = Wire(UInt((colSize * outputBufferTmpWidth).W))

  when(!finalCinValid) {
    // 使用默认接口（ s2 结果）
    final_outputEn := s2_outputWriteEn
    final_outputAddr := s2_outputWriteAddr
    final_outputData := s2_mergedDataBus
    final_jointEn := s2_jointWriteEn
    final_jointAddr := s2_jointWriteAddr
    final_jointData := s2_mergedDataBus
  }.otherwise {
    // 使用poolS结果
    final_outputEn := pool_writeValid && poolS_outputWriteEn
    final_outputAddr := pool_outputAddr
    final_outputData := pool_mergedDataBus

    final_jointEn := pool_writeValid && poolS_jointWriteEn
    final_jointAddr := pool_jointAddr
    final_jointData := pool_mergedDataBus
  }

  // outputSram接口Mux
  io.outputSramWrite.enable := final_outputEn
  io.outputSramWrite.address := final_outputAddr
  io.outputSramWrite.data := final_outputData

  // jointSram接口Mux
  io.jointSramWrite.enable := final_jointEn
  io.jointSramWrite.address := final_jointAddr
  io.jointSramWrite.data := final_jointData

  // Done signal logic - 与OutRouter完全一致
  val isLast = RegInit(false.B)
  val overFlag = RegInit(false.B)
  val doneFlag = RegInit(false.B)
  val doneValid = RegInit(false.B)
  
  // 判断是否是最后一次outputNoc数据传输
  when(io.actionMode.dataFlowMode){ // NVDIA模式
    when(s2_cout === pixelPara &&
        s2_position === groupNum) {
      isLast := true.B
    }
  }
  .otherwise { // FLOOD模式
    when((k =/= 0.U) && 
        (io.outputNoc.bits.count === 1.U) && 
        (io.outputNoc.bits.kernelRow === 0.U) && 
        (io.outputNoc.bits.cout === cout) &&
        (io.outputNoc.bits.featureMapLine === groupNum)) {
      isLast := true.B
    }
    when((k === 0.U) && 
        (s2_cout === cout) &&
        (s2_position === groupNum)) {
      isLast := true.B
    }
  }


  // 当coutCounter归零且完成最后一次握手时，标记overFlag
  // 当finalCinValid有效时，poolS流水级的有效标志其结束，因此需要判断poolS_valid；当finalCinValid无效时，直接判断s2Valid
  when(isLast && (s2_valid && !finalCinValid || poolS_valid && finalCinValid && !poolF_valid)) { // finalcinIdx时，流水级长度为7，超过tlatency，因此需要加入结果强判定!poolF_valid
    overFlag := true.B
  }
  
  // 当overFlag有效，在握手完成时，设置doneFlag
  when(overFlag && !(s2_valid && !finalCinValid || poolS_valid && poolS_valid && !poolF_valid)) {
    doneFlag := true.B
    isLast := false.B // s2Valid已经下拉，可以复位isLast
  }
  
  // done握手逻辑
  io.done.valid := doneValid
  io.done.bits := true.B
  
  when(doneFlag && !doneValid) {
    doneValid := true.B
    overFlag := false.B
  }.elsewhen(doneValid && io.done.ready) {
    doneValid := false.B
    doneFlag := false.B
  }

  // Ready signal for outputNoc (always ready for pipeline)
  io.outputNoc.ready := true.B

  // =============== Done 后清空新增流水级与池化缓存 ===============
  when(doneValid || doneFlag) {
    for (i <- 0 until poolsDataSize) {
      for (j <- 0 until colSize) {
        pools_datas(i)(j) := 0.S
      }
      compFlags(i) := false.B
    }
  }

  // 错误信号：不能在groupNum为奇数时，数据流模式还为FLOOD，且poolEn为1
  io.error := (groupNum(0) === 0.U) && (io.actionMode.dataFlowMode === 0.U) && (io.actionMode.poolEn === 1.U)
} 