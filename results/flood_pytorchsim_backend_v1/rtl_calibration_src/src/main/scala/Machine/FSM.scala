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
// Project    : FLOOD_Accelerator                                               //
// Module     : Cluster.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
//  Description: 多核架构的完整封装结构，用于：
//     1、根据Cluster内配置寄存器内信息可以计算得到以下CNN运算相关参数（与Cluster内各个Tile以及interNoc的配置信息相一致）：
//       1.1、interNoc的连接关系决定了当前MAC引擎的输出通道数（基本不会用到，可以忽略）；
//       1.2、inputNoc的systolic配置信息决定了当前MAC引擎（特征图Block）的输入通道数、特征图Block（Cluster内特征图的切块结构，一般按HW维度进行切块，C维度也可能会切块）的行数；
//       1.3、Tile内移位相加的配置信息决定了当前卷积运算的kernel窗口2D尺寸；
//       1.4、故可以由Cluster配置情况直接打到的三个卷积关键参数包括
//         1.4.1、特征图Block的通道数（也即匹配当前特征图Block的卷积核Block的输入通道数），
//         1.4.2、特征图Block的行数，
//         1.4.3、卷积核的Block（权重缓存内卷积核切块的区域结构，每个块在C维度与特征图块相对应，k维度不切块）的2D尺寸k
//       1.5、其它卷积相关配置参数包括：
//         1.5.1、卷积核Block的输出通道必然为1
//         1.5.2、特征图Block的列参数为config.colSize。
//     2、对MAC引擎（包括cluster与FSM，二者为并列关系）内配置寄存器中涉及卷积运算的所有参数进行汇总：
//       2.1、MAC引擎内Cluster内的特征图块参数（h，w，c） = （config.tileSize/groupSize(每组内Tile数量)，config.colSize，config.rowSize * groupSize）；
//       2.2、MAC引擎内FSM对应的卷积核块参数（k，k，cin，cout） = (k，k，config.tileSize/groupSize，cout)
//       2.3、注意：
//         2.3.1、cout为可配置参数，对应于权重缓存内的卷积核块的数量（权重SRAM内一个卷积核块精密排布，不同卷积核块相邻排布）
//         2.3.2、groupSize为可配置参数，可与config.tileSize计算得到Cluster内特征图块的通道数
//         2.3.3、k为可配置参数，必须与Cluster内Tile内移位相加的配置信息相一致
//     3、其中，FSM内的可配置参数有：k，groupSize，cout
//     4、FSM根据这两个可配置参数（CPU写入到寄存器内）计算得到卷积核相关参数，运转内部的循环状态机结构
//       4.1、第一层（最内层）循环：Cluster结构的输入写满（groupSize次写入）(对应卷积核参数的输入通道)
//       4.2、第二层循环：卷积核2D结构一行的遍历（k次写满）
//       4.3、第三层循环：卷积核所有行的遍历（k次行遍历）
//       4.4、第四层循环：卷积核块的遍历（cout次行遍历）
//       4.5、运转情况：
//         4.5.1、k=1时跳过第2、3层循环结构
//         4.5.2、k>1时，第2、3层循环结构正常运转
//     5、FSM一边运转，一边进行乒乓权重缓存、乒乓特征图缓存、乒乓配置缓存、乒乓输出缓存的乒乓更新
//     6、由于卷积核尺寸可重构（1-16），运算时可能发生输出缓存消耗完全而权重缓存尚未使用完全的情况，故而输出缓存的乒乓更新需要与权重缓存解耦合；同理，Cluster的乒乓更新也需与权重缓存相解耦。
//     7、报错：
//       7.1、当inputNoc长时间未相应时，发生超时报错Cluster内Tile组内Tile数量过多时，发生超时报错

// Modification History:                             
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-06-15 |   陈挺然    |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.machine

import chisel3._
import chisel3.util._
import FLOOD_Accelerator.core.Config
import FLOOD_Accelerator.sram.pingpongBuffer

class FSM extends Module {
  // 从Config对象获取参数
  val weightBandWidth = Config.weightBandWidth
  val colSize = Config.colSize
  val rowSize = Config.rowSize
  val dataWidth = Config.dataWidth
  val outputWidth = Config.outputWidth
  val tileSize = Config.tileSize
  val pipeline = Config.pipeline
  val tLatency = Config.tLatency
  val configDataWidth = Config.configDataWidth

  // 配置参数位宽定义
  val kernelBlockKWidth = log2Ceil(Config.maxKernelBlockK)             // 卷积核尺寸 (最大16)
  val kernelBlockCoutWidth = log2Ceil(Config.maxKernelBlockCout)       // 输出通道数（卷积核Block块数）（最大256）
  val groupSizeWidth = log2Ceil(Config.maxGroupSize)              // 每组Tile数量 (最大16)
  val groupNumWidth = log2Ceil(Config.maxGroupNum)              // 组数 (最大16)
  val cinIdxWidth = log2Ceil(Config.maxKernelBlockCin/Config.rowSize + 1)  // 输入通道数（以rowSize个并行度为配置的最小单元）（输入通道最大值4096）
  val colIdxWidth = log2Ceil(Config.maxResolutionCol/Config.colSize + 1)  // 列向组数（以colSize个并行度为配置的最小单元）（特征图宽度最大值4096）
  val workModeWidth = log2Ceil(Config.maxWorkMode)  // 工作模式位宽
  // 新增 stride 字段位宽（作用：k=1 的场景下，对权重地址基数做倍乘；k!=1 时视为0）
  val strideWidth = kernelBlockKWidth // stride最大为k
  // Nvdla REG字段位宽
  val featBlkWidWidth = log2Ceil(Config.maxFeatureBlockWidth) // featBlkWid位宽
  val pixelParaWidth = log2Ceil(Config.maxPixelParallel) // pixelPara位宽
  
  // 参数检查
  require(configDataWidth >= kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCoutWidth + strideWidth, "Normal配置寄存器位宽不足") // Normal配置寄存器：k, groupSize, groupNum, cout, stride
  require(configDataWidth >= cinIdxWidth + colIdxWidth + workModeWidth, "Special配置寄存器位宽不足") // Special配置寄存器：cinIdx, colIdx, workMode


  // IO定义
  val io = IO(new Bundle {
    // 乒乓控制信号
    val pingpong = Input(Bool())

    // 数据流模式控制信号
    val dataflowMode = Input(Bool())  // false: Flood, true: NVDIA

    // 配置总线接口
    val configBus = new Bundle {
      val data = Input(UInt(configDataWidth.W))
      val addr = Input(UInt(Config.configAddrWidth.W))
      val en = Input(Bool())
    }

    // 与Cluster的输入Noc对接的接口
    val inputNoc = Decoupled(new Bundle {
      val data = Vec(rowSize, SInt(dataWidth.W))
      val writeId = UInt(Config.idWidth.W)
      val writeIdNext = UInt(Config.idWidth.W)
      val count = UInt(8.W)
      val inputMode = UInt(8.W)
      val cout = UInt(pixelParaWidth.W)  // 添加cout信号域
      val kernelRow = UInt(kernelBlockKWidth.W)  // 添加kernelRow信号域
      val remain = UInt(8.W)
    })
    val inputNocReady = Input(Bool())

    // 与权重缓存对接的接口
    val weightSramRead = new Bundle {
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(log2Ceil(Config.weightSramLength).W))
      val readData = Input(UInt((rowSize * dataWidth).W))
    }

    // 异常标志
    val error = Output(Bool())

    // 流水线启动-完成握手接口
    val start = Flipped(Decoupled(Bool()))
    val done = Decoupled(Bool())
  })

  // 配置寄存器 - 使用 Reg 存储（增加默认初值）
  // Normal: {remain, stride, cout, groupNum, groupSize, k}
  private val defaultK = 2.U(kernelBlockKWidth.W)  // 默认k=3
  private val defaultGroupSize = 0.U(groupSizeWidth.W)  // 默认groupSize=1
  private val defaultGroupNum = (Config.tileSize-1).U(groupNumWidth.W)  // 默认groupNum=tileSize
  private val defaultCout = 15.U(kernelBlockCoutWidth.W)  // 默认cout=16
  private val defaultStride = 0.U(strideWidth.W)  // 默认stride=1
  private val normalUsedWidth = kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCoutWidth + strideWidth
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

  // Special: {remain, workMode, colIdx, cinIdx}
  private val defaultCinIdx = 0.U(cinIdxWidth.W)  // 默认cinIdx=0
  private val defaultColIdx = 0.U(colIdxWidth.W)  // 默认colIdx=0
  private val defaultWorkMode = 0.U(workModeWidth.W)  // 默认workMode=0
  private val specialUsedWidth = cinIdxWidth + colIdxWidth + workModeWidth
  private val specialRemainWidth = configDataWidth - specialUsedWidth
  private val defaultSpecialPacked = Cat(
    0.U(specialRemainWidth.W),
    defaultWorkMode,
    defaultColIdx,
    defaultCinIdx
  )
  val configRegSpecial = RegInit(defaultSpecialPacked)

  // 写配置逻辑
  when(io.configBus.en) {
    when(io.configBus.addr === Config.FSMRouterConfIdStart.U) {
      configRegNormal := io.configBus.data
    }.elsewhen(io.configBus.addr === Config.FSMRouterConfIdEnd.U) {
      configRegSpecial := io.configBus.data
    }
  }

  // 从Normal配置寄存器中获取k、groupSize、groupNum、cout、stride
  val k = configRegNormal(kernelBlockKWidth-1, 0) // 卷积核尺寸
  val groupSize = configRegNormal(kernelBlockKWidth + groupSizeWidth - 1, kernelBlockKWidth) // Cluster内每个Tile组内的Tile数量
  val groupNum = configRegNormal(kernelBlockKWidth + groupSizeWidth + groupNumWidth - 1, kernelBlockKWidth + groupSizeWidth) // 组数
  val cout = configRegNormal(kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCoutWidth - 1, kernelBlockKWidth + groupSizeWidth + groupNumWidth) // 输出通道数
  val stride = configRegNormal(kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCoutWidth + strideWidth - 1,
                               kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCoutWidth)

  // 从Special配置寄存器中获取CinIdx等参数
  val cinIdx = configRegSpecial(cinIdxWidth - 1, 0) // 当前特征图Block的输入通道组序号
  val colIdx = configRegSpecial(cinIdxWidth + colIdxWidth - 1, cinIdxWidth) // 当前特征图Block的列向组序号
  val workMode = configRegSpecial(cinIdxWidth + colIdxWidth + workModeWidth - 1, cinIdxWidth + colIdxWidth) // 当前工作模式
  
  // Error 检查1：k 不能大于 2倍groupNum
  val errorFlag1 = k > (groupNum << 1 + 1)

  // 状态机状态定义 - 简化为4个状态
  val sIdle :: sWork :: sDone :: sError :: Nil = Enum(4)
  val state = RegInit(sIdle)

  // 计数器 - 修正位宽定义
  val inputGroupCnt = RegInit(0.U(groupSizeWidth.W))
  val kernelColCnt = RegInit(((1<<kernelBlockKWidth)-1).U(kernelBlockKWidth.W))
  val kernelRowCnt = RegInit(((1<<kernelBlockKWidth)-1).U(kernelBlockKWidth.W))
  val outputChannelCnt = RegInit(0.U(kernelBlockCoutWidth.W))
  val timeoutCnt = RegInit(0.U(8.W))  // 256个时钟周期的超时计数器
  val timeoutFlag = timeoutCnt(7) // 超时标志
  
  // 权重SRAM地址寄存器 - 用于提前一个时钟周期更新地址
  val weightSramAddrReg = RegInit(0.U(log2Ceil(Config.weightSramLength).W))
  
  // inputNoc.valid寄存器 - 解决时序问题
  val inputNocValidReg = RegInit(false.B)
  // 记录上一个周期的ready/valid信号
  val prevReady = RegNext(io.inputNoc.ready, false.B)
  val prevValid = RegNext(io.inputNoc.valid, false.B)
  // 检测握手沿：ready高->低且valid高
  val handshakeFired = prevReady && prevValid && !io.inputNoc.ready

    // 下一个步进时各个计数器的值
  val nextInputGroupCnt = Mux(inputGroupCnt === groupSize, 0.U, inputGroupCnt + 1.U)
  val nextKernelColCnt = Mux(inputGroupCnt === groupSize, 
                            Mux(kernelColCnt === 0.U, k, kernelColCnt - 1.U), 
                            kernelColCnt)
  val nextKernelRowCnt = Mux(inputGroupCnt === groupSize,
                            Mux(kernelColCnt === 0.U,
                                Mux(kernelRowCnt === 0.U, k, kernelRowCnt - 1.U),
                                kernelRowCnt),
                            kernelRowCnt)
  val nextOutputChannelCnt = Mux(inputGroupCnt === groupSize,
                                  Mux(kernelColCnt === 0.U,
                                      Mux(kernelRowCnt === 0.U,
                                          Mux(outputChannelCnt === cout, 0.U, outputChannelCnt + 1.U),
                                          outputChannelCnt),
                                      outputChannelCnt),
                              outputChannelCnt)

  // 读取地址计算
  val baseAddrCout = nextOutputChannelCnt * (groupSize+&1.U) * (k+&1.U) * (k+&1.U)
  val baseAddrCinIdx = cinIdx * (cout+&1.U) * (groupSize+&1.U) * (k+&1.U) * (k+&1.U)
  // stride 的“表现值”：当 k==0（NVDLA数据流模式）时为 stride，否则为0
  val strideEffective = Mux(k === 0.U, stride, 0.U)
  // 对基地址做倍乘：* (strideEffective + 1)
  val baseAddr = baseAddrCout +& baseAddrCinIdx
  // 权重SRAM地址计算函数
  def calculateWeightSramAddr(
    kernelRowCnt: UInt,
    kernelColCnt: UInt,
    inputGroupCnt: UInt,
    k: UInt,
    groupSize: UInt
  ): UInt = {
    // 地址计算：outputChannel * (k*k*groupSize) + kernelRow * (k*groupSize) + kernelCol * groupSize + inputGroup
    baseAddr * (strideEffective + 1.U) +&  // 作stride的像素移位倍乘：* (strideEffective + 1)，仅在k=0（NVDLA数据流模式）时可能有效
    kernelRowCnt * (k+&1.U) * (groupSize+&1.U) +  
    kernelColCnt * (groupSize+&1.U) +&
    inputGroupCnt
  }

  // 先给所有输出信号赋默认值
  io.inputNoc.valid := inputNocValidReg
  // 将UInt类型的权重数据转换为Vec类型的SInt数据
  for (i <- 0 until rowSize) {
    val startBit = i * dataWidth
    val endBit = startBit + dataWidth - 1
    io.inputNoc.bits.data(i) := io.weightSramRead.readData(endBit, startBit).asSInt
  }
  io.inputNoc.bits.writeIdNext := inputGroupCnt
  io.inputNoc.bits.writeId := inputGroupCnt
  io.inputNoc.bits.count := 0.U
  io.inputNoc.bits.inputMode := Mux(kernelRowCnt === 0.U && kernelColCnt === 0.U, 1.U, 0.U)
  io.inputNoc.bits.remain := 0.U
  io.inputNoc.bits.cout := outputChannelCnt  // 使用当前输出通道计数器值
  io.inputNoc.bits.kernelRow := kernelRowCnt  // 使用当前kernelRow计数器值
  io.weightSramRead.readEnable := (state === sWork) && io.inputNoc.ready && !io.inputNoc.valid // 在work状态且准备发送数据时使能权重SRAM
  io.weightSramRead.readAddress := weightSramAddrReg

  // 状态机逻辑 - 四层嵌套循环都在work状态中
  switch(state) {
    is(sIdle) {
      when(io.start.valid && io.start.ready) { // ready为高电平有效，表示FSM可以被start
        // 初始化计数器
        inputGroupCnt := 0.U
        kernelColCnt := k
        kernelRowCnt := k
        outputChannelCnt := 0.U
        
        // 初始化超时计数器
        timeoutCnt := 0.U

        // 初始化权重SRAM地址寄存器
        weightSramAddrReg := calculateWeightSramAddr(
          k,
          k,
          0.U,
          k,
          groupSize
        )
        // 初始化valid寄存器
        inputNocValidReg := false.B
        state := sWork
      }
    }

    is(sWork) {
      // FSM特殊握手时序：ready->valid->!ready->!valid
      when(!io.inputNoc.ready && io.inputNoc.valid) { // 此时握手已经完成，可以进行步进，valid高而ready由高变低
        // 步进：更新权重SRAM地址和计数器
        inputGroupCnt := nextInputGroupCnt
        kernelColCnt := nextKernelColCnt
        kernelRowCnt := nextKernelRowCnt
        outputChannelCnt := nextOutputChannelCnt
        when(k === 0.U && inputGroupCnt === groupSize && outputChannelCnt === cout){
          state := sDone
        }.elsewhen(inputGroupCnt === groupSize && kernelColCnt === 0.U && kernelRowCnt === 0.U && outputChannelCnt === cout) {
          state := sDone
        }

        // 步进时，准备下一个权重SRAM地址（使用步进后的计数器值）
        weightSramAddrReg := calculateWeightSramAddr(
          nextKernelRowCnt,
          nextKernelColCnt,
          nextInputGroupCnt,
          k,
          groupSize
        )
        // 拉低valid
        inputNocValidReg := false.B
      }.elsewhen(io.inputNoc.ready && !io.inputNoc.valid) { 
        // ready高且valid低，准备下一组数据，拉起valid
        inputNocValidReg := true.B
        // 权重SRAM地址已在上一个握手沿更新，无需重复
        // ready高，清空timeout计数器
        timeoutCnt := 0.U
      }.elsewhen(io.inputNoc.ready && io.inputNoc.valid) {  // 握手
        // ready高，清空timeout计数器
        timeoutCnt := 0.U
      }.elsewhen(!io.inputNoc.ready && !io.inputNoc.valid) { // 等待下次ready有效
        // ready低且valid低，什么都不做
        inputNocValidReg := false.B
        timeoutCnt := timeoutCnt + 1.U
      }
      // 超时检测 - 只在work状态时检测超时
      when(timeoutFlag || errorFlag1) {
        state := sError
      }
    }

    is(sDone) {
      when(io.done.ready) { 
        state := sIdle
      }
    }

    is(sError) {
      state := sIdle // 回到空闲状态
    }
  }
  
  io.error := (state === sError)
  io.done.valid := (state === sDone)
  io.done.bits := true.B
  io.start.ready := state === sIdle // FSM对外的ready信号为高有效，表示FSM可以接收输入数据
}

