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
//       • 初始列向拼接(01): 表示特征图Block为非顶端最左侧Block
//       • 一般列向拼接(10)：表示特征图为非顶端非左侧Block
//       • 仅输入通道补齐(11)：表示特征图为cin!=0的Block
//       • 默认情况为不补齐也不拼接(00)：特征图为顶端最左侧，cin=0的Block
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
import FLOOD_Accelerator.sram.pingpongBuffer

class OutRouterPlane(
  val tileId: Int
) extends Module {
  // Inherit parameters from Config
  val colSize = Config.colSize
  val tileSize = Config.tileSize
  val outputWidth = Config.outputWidth
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
  val resolutionColIdxWidth = log2Ceil(Config.maxResolutionCol/Config.colSize + 1)
  val workModeWidth = 2  // Added for work mode configuration

  // IO definition
  val io = IO(new Bundle {
    // Inherited from OutRouter
    val pingpong = Input(Bool())
    // 配置总线
    val configBus = new Bundle {
      val data = Input(UInt(configDataWidth.W))
      val addr = Input(UInt(Config.configAddrWidth.W))
      val en = Input(Bool())
    }
    // 输出Noc接口
    val outputNoc = Flipped(Decoupled(new Bundle {
      val data = Vec(colSize, SInt(finalWidth.W))
      val featureMapLine = UInt((2*log2Ceil(tileSize)).W)
      val count = UInt(8.W)
      val cout = UInt(kernelBlockCoutWidth.W)
      val kernelRow = UInt(kernelBlockKWidth.W)
      val remain = UInt(16.W)
    }))
    // 完成信号
    val done = Decoupled(Bool())
  
    // outputSram写接口
    val outputSramWrite = new Bundle {
      val enable = Output(Bool())
      val address = Output(UInt(outputAddrWidth.W))
      val data = Output(UInt((colSize * outputBufferDataWidth).W))
    }
    // outputSram读接口
    val outputSramRead = new Bundle {
      val enable = Output(Bool())
      val address = Output(UInt(outputAddrWidth.W))
      val data = Input(UInt((colSize * outputBufferDataWidth).W))
    }
    // jointSram写接口
    val jointSramWrite = new Bundle {
      val enable = Output(Bool())
      val address = Output(UInt(jointAddrWidth.W))
      val data = Output(UInt((colSize * outputBufferDataWidth).W))
    }
    // jointSram读接口
    val jointSramRead = new Bundle {
      val enable = Output(Bool())
      val address = Output(UInt(jointAddrWidth.W))
      val data = Input(UInt((colSize * outputBufferDataWidth).W))
    }
  })

  // Configuration buffer with workMode support
  val configBuffer = Module(new pingpongBuffer(
    size = 1,
    dataWidth = configDataWidth,
    bandWidth = configDataWidth
  ))
  configBuffer.io.pingpong := io.pingpong
  configBuffer.io.writeEnable := io.configBus.en && (io.configBus.addr === tileId.U)
  configBuffer.io.writeAddress := 0.U
  configBuffer.io.writeData := io.configBus.data
  configBuffer.io.readEnable := true.B

  // Parse configuration with workMode
  val k = configBuffer.io.readData(kernelBlockKWidth-1, 0)
  val groupSize = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth - 1, kernelBlockKWidth)
  val groupNum = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth + groupNumWidth - 1, 
                                         kernelBlockKWidth + groupSizeWidth)
  val cinIdx = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth + groupNumWidth + cinIdxWidth - 1,
                                    kernelBlockKWidth + groupSizeWidth + groupNumWidth)
  val cout = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth + groupNumWidth + cinIdxWidth + 
                                     kernelBlockCoutWidth - 1,
                                     kernelBlockKWidth + groupSizeWidth + groupNumWidth + cinIdxWidth)
  val resolutionColIdx = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth + groupNumWidth + cinIdxWidth + 
                                              kernelBlockCoutWidth + resolutionColIdxWidth - 1,
                                              kernelBlockKWidth + groupSizeWidth + groupNumWidth + cinIdxWidth + 
                                              kernelBlockCoutWidth)
  val workMode = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth + groupNumWidth + cinIdxWidth + 
                                         kernelBlockCoutWidth + resolutionColIdxWidth + workModeWidth - 1,
                                         kernelBlockKWidth + groupSizeWidth + groupNumWidth + cinIdxWidth + 
                                         kernelBlockCoutWidth + resolutionColIdxWidth)

  // Data truncation function (same as original OutRouter)
  def truncateData(dataVec: Vec[SInt], inWidth: Int, outWidth: Int): Vec[SInt] = {
    val truncateData = Wire(Vec(colSize, SInt(outWidth.W)))
    val tmpData = Wire(Vec(colSize, UInt(outWidth.W)))
    for (i <- 0 until colSize) {
      tmpData(i) := dataVec(i).asUInt(inWidth-1, inWidth-outWidth)
      truncateData(i) := tmpData(i).asSInt
    }
    truncateData
  }

  // Pipeline stage prepare: Address calculation
  // Base address calculations
  val outputBaseAddr = (io.outputNoc.bits.cout * (groupNum +& 1.U)) << 1
  val jointBaseAddr = resolutionColIdx * (cout+1.U) * k + io.outputNoc.bits.cout * k // 每次写入的基地址
  val jointBufferBias = (Config.maxResolutionCol/Config.colSize + 1).U * (cout + 1.U) * k // 拼接缓存区的基地址偏移量

  // Write enable conditions
  val position = Mux(io.outputNoc.valid, io.outputNoc.bits.featureMapLine + (k - io.outputNoc.bits.kernelRow), 0.U)
  
  val outputWriteEn = io.outputNoc.valid && 
                     (position <= groupNum) 
                     
  val jointWriteEn = io.outputNoc.valid && 
                    (position > groupNum) 

  // Write address calculations
  val outputWriteAddr = Mux(outputWriteEn, outputBaseAddr +& 
                       ((k - io.outputNoc.bits.kernelRow) << 1) +& 
                       (io.outputNoc.bits.featureMapLine << 1) +& 
                       io.outputNoc.bits.count, 0.U)
  val jointWriteAddr = Mux(jointWriteEn,
                        jointBaseAddr + (position-groupNum-1.U) + 
                        Mux(io.outputNoc.bits.count === 0.U, 0.U, jointBufferBias), 0.U)

  // Read address and enable calculations
  // 需要读取数据的情况
  // 初始列向拼接：workMode === 1.U
  // 一般列向拼接：workMode === 2.U
  // 仅输入通道补齐：workMode === 3.U

  // 标志信号
  val groupNumLowerThanK = groupNum < k
  val needRead = workMode === 1.U || workMode === 2.U || workMode === 3.U
  
  // 读地址计算
  val outputReadAddr = Mux(workMode === 3.U, outputWriteAddr,
                         Mux(workMode === 2.U && position <= groupNum && io.outputNoc.bits.count === 0.U,
                             outputWriteAddr + 1.U, 0.U))

  // 拼接缓存读地址计算
  // 高向拼接
  val jointHeightReadAddr = Mux(workMode === 3.U, jointWriteAddr, // 通道补齐
                          Mux((workMode === 2.U || workMode === 1.U) && position < k, // 高向拼接（joint结果区，拼接缓存区都要更新）
                              jointBaseAddr + position + Mux(io.outputNoc.bits.count === 0.U, 0.U, jointBufferBias), 0.U))
  // 列向拼接
  val jointWidthReadAddr = Mux(workMode === 2.U && position > groupNum && io.outputNoc.bits.count === 0.U, // 列向拼接（只有预期写入joint结果区内的数据要拼接读取）
                            jointBaseAddr + position + jointBufferBias, 0.U)

  val outputReadEn = needRead && io.outputNoc.valid &&
                    (workMode === 3.U && outputWriteEn || 
                     workMode === 2.U && position <= groupNum && io.outputNoc.bits.count === 0.U && outputWriteEn)
                   
  val jointHeightReadEn = needRead && io.outputNoc.valid && // 高向拼接或通道补齐读使能（S1）
                   (workMode === 3.U && position > groupNum || // 通道补齐
                    (workMode === 2.U || workMode === 1.U) && position < k && !groupNumLowerThanK ||  // 高向拼接（groupNum >= k 的情况）
                    (workMode === 2.U || workMode === 1.U) && position < k && groupNumLowerThanK) // 高向拼接（groupNum < k 的情况）
  
  val jointWidthReadEn = needRead && io.outputNoc.valid && // 列向拼接读使能(S2)
                    (workMode === 2.U && position > groupNum && io.outputNoc.bits.count === 0.U) // 列向拼接

  // pipeline stage 0: 空流水级，规避行读与列读重叠的情况
  val s0_valid = RegNext(io.outputNoc.valid, false.B)
  val s0_currentData = RegNext(io.outputNoc.bits.data)
  val s0_outputWriteAddr = RegNext(outputWriteAddr)
  val s0_outputWriteEn = RegNext(outputWriteEn)
  val s0_jointWriteAddr = RegNext(jointWriteAddr)
  val s0_jointWriteEn = RegNext(jointWriteEn)
  val s0_workMode = RegNext(workMode)
  val s0_outputReadEn = RegNext(outputReadEn)
  val s0_jointHeightReadEn = RegNext(jointHeightReadEn)
  val s0_jointHeightReadAddr = RegNext(jointHeightReadAddr)
  val s0_jointWidthReadEn = RegNext(jointWidthReadEn)
  val s0_jointWidthReadAddr = RegNext(jointWidthReadAddr)

  // Pipeline stage 1: 充当通道补齐/高拼接/position<=groupNum时的列拼接  三种读取行为的读取缓冲(1clk)，列拼接读请求发送，同时完成通道补齐/高拼接的读取结果累加
  val s1_valid = RegNext(s0_valid, false.B)
  val s1_currentData = RegNext(s0_currentData)
  val s1_outputWriteAddr = RegNext(s0_outputWriteAddr)
  val s1_outputWriteEn = RegNext(s0_outputWriteEn)
  val s1_jointWriteAddr = RegNext(s0_jointWriteAddr)
  val s1_jointWriteEn = RegNext(s0_jointWriteEn)
  val s1_workMode = RegNext(s0_workMode)
  val s1_outputReadEn = RegNext(s0_outputReadEn)
  val s1_jointHeightReadEn = RegNext(s0_jointHeightReadEn) 
  val s1_jointWidthReadEn = RegNext(s0_jointWidthReadEn)
  val s1_jointWidthReadAddr = RegNext(s0_jointWidthReadAddr)

  // 通道补齐/高拼接的读取结果累加
  // Helpers to unpack bus to Vec
  def unpackBusToVec(bus: UInt): Vec[UInt] = {
    val vec = Wire(Vec(colSize, UInt(outputBufferDataWidth.W)))
    for (i <- 0 until colSize) {
      vec(i) := bus((i+1)*outputBufferDataWidth-1, i*outputBufferDataWidth)
    }
    vec
  }
  val zeroVec = VecInit(Seq.fill(colSize)(0.U(outputBufferDataWidth.W)))
  // Select which read data to use
  val s1_jointReadData = Mux(s1_jointHeightReadEn, unpackBusToVec(io.jointSramRead.data), zeroVec)
  val s1_outputReadData = Mux(s1_outputReadEn, unpackBusToVec(io.outputSramRead.data), zeroVec)
  
  // Element-wise addition for vector data
  val s1_mergedData = Wire(Vec(colSize, SInt((finalWidth+2).W))) // 预留加法进位
  
  // Element-wise addition with conditional selection
  for (i <- 0 until colSize) {
    s1_mergedData(i) := s1_currentData(i) +& s1_jointReadData(i).asSInt +& s1_outputReadData(i).asSInt
  }

  // Pipeline stage 2: 将position>groupNum时的列拼接的读取结果累加，并写回
  val s2_valid = RegNext(s1_valid, false.B)
  val s2_currentData = RegNext(s1_mergedData)
  val s2_outputWriteAddr = RegNext(s1_outputWriteAddr)
  val s2_outputWriteEn = RegNext(s1_outputWriteEn)
  val s2_jointWriteAddr = RegNext(s1_jointWriteAddr)
  val s2_jointWriteEn = RegNext(s1_jointWriteEn)
  val s2_workMode = RegNext(s1_workMode)
  val s2_jointWidthReadEn = RegNext(s1_jointWidthReadEn)

  // Select which read data to use
  val s2_jointReadData = Mux(s1_jointWidthReadEn, unpackBusToVec(io.jointSramRead.data), zeroVec)
  
  // Element-wise addition for vector data
  val s2_mergedData = Wire(Vec(colSize, SInt((finalWidth+2).W)))
  
  // Element-wise addition with conditional selection
  for (i <- 0 until colSize) {
    s2_mergedData(i) := s2_currentData(i) +& s2_jointReadData(i).asSInt
  }

  // 准备vector to bus转换
  val s2_mergedDataUInt = Wire(Vec(colSize, UInt((outputBufferDataWidth).W)))
  for (i <- 0 until colSize) {
    s2_mergedDataUInt(i) := s2_mergedData(i).asUInt
  }

  // Read from SRAMs
  // 在outputValid后通道补齐/高拼接立即发出读请求
  io.outputSramRead.enable := io.outputNoc.valid && outputReadEn
  io.outputSramRead.address := outputReadAddr
  io.jointSramRead.enable := (io.outputNoc.valid && jointHeightReadEn) || (s1_valid && s1_jointWidthReadEn)
  io.jointSramRead.address := Mux(s1_valid && s1_jointWidthReadEn, s1_jointWidthReadAddr, Mux(io.outputNoc.valid && jointHeightReadEn, jointHeightReadAddr, 0.U))

  // Write to SRAMs
  // pack Vec to bus
  def packVecToBus(vec: Vec[UInt]): UInt = {
    val bus = Wire(UInt((colSize * outputBufferDataWidth).W))
    var acc = 0.U((colSize * outputBufferDataWidth).W)
    for (i <- 0 until colSize) {
      acc = acc | (vec(i) << (i * outputBufferDataWidth).U)
    }
    bus := acc
    bus
  }
  io.outputSramWrite.enable := s2_valid && s2_outputWriteEn
  io.outputSramWrite.address := s2_outputWriteAddr
  io.outputSramWrite.data := Mux(s2_valid && s2_outputWriteEn, packVecToBus(s2_mergedDataUInt) , 0.U((colSize * outputBufferDataWidth).W))

  io.jointSramWrite.enable := s2_valid && s2_jointWriteEn
  io.jointSramWrite.address := s2_jointWriteAddr
  io.jointSramWrite.data := Mux(s2_valid && s2_jointWriteEn, packVecToBus(s2_mergedDataUInt), 0.U((colSize * outputBufferDataWidth).W))

  // Done signal logic - 与OutRouter完全一致
  val isLast = RegInit(false.B)
  val overFlag = RegInit(false.B)
  val doneFlag = RegInit(false.B)
  val doneValid = RegInit(false.B)
  
  // 判断是否是最后一次outputNoc数据传输
  when((io.outputNoc.bits.count === 1.U) && 
      (io.outputNoc.bits.kernelRow === 0.U) && 
      (io.outputNoc.bits.cout === cout) &&
      (io.outputNoc.bits.featureMapLine === groupNum)) {
    isLast := true.B
  }

  // 当coutCounter归零且完成最后一次握手时，标记overFlag
  when(isLast && s2_valid) {
    overFlag := true.B
  }
  
  // 当overFlag有效，在握手完成时，设置doneFlag
  when(overFlag && !s2_valid) {
    doneFlag := true.B
    isLast := false.B // s2_valid已经下拉，可以复位isLast
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
} 