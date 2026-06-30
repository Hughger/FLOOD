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
// Module     : Tile.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: 多核架构的一个封装组件单元，用于：
    // 1、维护CIMCore的数据及工作状态
    // 2、对CIMcore的输出进行加工处理
    // 3、完成核间互联协议的运算部分// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.core

import chisel3._
import chisel3.util._
import scala.math._
import FLOOD_Accelerator.core.CIMCore
import FLOOD_Accelerator.sram.pingpongBuffer
import FLOOD_Accelerator.sram.vector

//////////////////////////////////////////////////////////////////////////////
// Project    : FLOOD_Accelerator                                               //
// Module     : Tile.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: Tile结构，将CIMCore封装，并封装如分布式的累加、通信、数据一致性等功能
// 1、宏参数： inputBandWidth(输入数据带宽), outputBandWidth(输出数据带宽), WeightBandWidth(权值数据写入带宽), colSize(CIMCore的列数), rowSize(CIMCore的行数), dataWidth(CIMCore输入数据位宽), outputWidth(CIMCore输出数据位宽)，TileSize(多核架构中的Tile的数量)，
// 2、功能：
//     2.1、维护CIMCore的数据及工作状态
//         2.1.1、根据系统Tile总数，确定核间NOC通信的数据位宽
//         2.1.2、根据colSize参数与outputWidth参数与参数，确定移位相加寄存器的尺寸(colSize+TileSize)与每个元素的位宽(outputWidth+log2ceil(TileSize)
//         2.1.3、根据TileSize参数与outputWidth参数，确定累加寄存器的元素个数(移位相加寄存器的尺寸)、元素位宽(outputWidth+log2ceil(TileSize))
//         2.1.4、每个Tile有唯一的TileID，由TileSize来计算TileID的bit位宽
//         2.1.4、若干配置寄存器，存储Tile的InputID 输入数据写入通过匹配这个WriteID来实现Tile片选
//         2.1.5、配置寄存器更新依赖一个全局的配置总线，所有Tile共享，通过其上ID信息与TileID的匹配来实现Tile片选
//         2.1.6、输入NoC是一个广播NoC，故所有Tile的输入NoCInterface均对接同一个输入NoCInterface模块，其上数据包包含ID信息，与之匹配
//         2.1.7、权重更新依赖一个全局的权重总线，所有Tile共享，通过其上ID信息与TileID的匹配来实现Tile片选
//         2.1.8、配置寄存器同样为乒乓，基于pingpongBuffer模块实现
//         2.1.9、inputBandWidth若不等于dataWidth*rowSize，则一次输入NoC输入不能满足CIMCore的输入需求，则需要Tile内生成一个FIFO，并使用FIFO的empty信号来与CIMCore进行握手、并使用FIFO的full信号来与输入NoC进行握手。由于需要输入NoC多次输入来满足CIMCore的输入需求，故输入数据包应包含计数信息，表示当前输入次数，提示Tile当前输入应当存储在FIFO的哪个位置。
//         2.1.10、根据WeightBandWidth、colSize、rowSize、dataWidth，计算权重更新时的地址总线位宽
//         2.1.11、根据colSize、rowSize、dataWidth，TileSize，计算整个多核系统的权重总数，并根据权重总数与WeightBandWidth，计算权重更新时的总时间，根据所有Tile配置信息更新的总时间<权重跟新总时间,计算合适的配置总线位宽
//         2.1.12、Tile在满足条件时主动向输出NoC Interface发起握手，若outputBandWidth不满足一次完全输出整个结果向量（每个输出结果元素的位宽为（outputWidth + log2ceil(TileSize）），则需要Tile来多次输出，且在输出包的计数信息域中用于记录输出次数
//         2.1.13、输入NoC Interface提供的数据包包含写入ID信息、输入次数信息、写入数据信息，remain信息
//         2.1.14、输出NoC Interface提供的数据包包含TileID信息、输出次数信息、输出数据信息，remain信息
//         2.1.15、配置寄存器内包含kernelSize信息（8bit）、inputID信息(log2ceil(TileSize) bit）、remain信息（16bit）、工作状态信息（32-8-log2ceil(TileSize)-16) bit，必须大于等于0否则报错）表明当前Tile的工作模式，默认全0表示处于卷积工作状态
//      2.2、对其输出进行加工处理
//         2.2.1、根据配置寄存器信息决定是否对CIMCore的结果进行移位相加（向量元素（每个元素为dataWidth个bit）级移位）,结果保存在一个2*colSize的移位相加寄存器中，称为CIMFSMResult
//         2.2.2、根据配置寄存器信息中的kernelSize，确定移位相加次数
//             2.2.3.1、移位相加次数为0时，直接输出CIMCore结果
//             2.2.3.2、移位相加次数为N时，执行N次移位相加
//         2.2.3、移位相加次数完成后，拉起握手信号，握手完成后，清空移位相加寄存器，并清空移位相加计数器
//     2.3、向NoCInterface发送数据（每个Tile有二个互联NoCInterface（下方、上方），第0个Tile向上的互联NoCInterface没有连接互联NoC Interface模块，第15个Tile向下的互联NoCInterface没有连接互联NoC Interface模块,其余上下相邻的Tile间通过一个互联NoCInterface连接）
//         2.3.1、如果上方互联NoC Interface的router信息中发送信号有效，则发送CIMFinalResult结果给上方的互联NoC Interface 模块
//         2.3.2、如果下方互联NoC Interface的router信息中发送信号有效，则等待下方互联NoC Interface 的数据到来后，与CIMFSMResult结果累加后形成CIMFinalResult结果(否则CIMFSMResult结果即为CIMFinalResult结果)
//         2.3.3、根据四个互联NoCInterface的router信息，确定对接方式
//             2.3.3.1、16个Tile之间对接一个互联NoC Interface模块(故为15个互联NoC Interface模块)，连接方式按S型连接（实际上就是16个Tile上下连接，但因为电路面积的需求，需要摆成4×4 的阵列）（左上角的Tile是第0个Tile，右下角是第15个Tile）
//             2.3.3.2、每个NoCInterface模块内有配置寄存器存有router信息，确定对接方式
//                 2.3.3.2.1、每个互联NoCInterface的router信息有4个bit
//                     2.3.3.2.1.1、最高位表示是否发送，deliver=1表示发送，deliver=0表示不发送
//                     2.3.3.2.1.2、次高位表示发送方式是累加还是systolic, systolic=0表示累加，systolic=1表示systolic
//                     2.3.3.2.1.3、末2 bits预留,为remain
//                     2.3.3.2.1.4、每个互联NoCInterface必须连接上下两个Tile，两个Tile有相同的deliver信号以及systolic信号
//             2.3.3.3、每个Tile根据上下两个互联NoCInterface的router信息的，组成2bit deliver信号 确定发送情况
//             2.3.3.4、根据4个互联NoCInterface的router信息的，组成2bit direction信号 确定发送方向
//                 2.3.3.4.1、direction信号与deliver信号按位与后为2bit的connect信号(第0bit表示下方互联NoCInterface，第1bit表示上方互联NoCInterface)
//                 2.3.3.4.2、每个Tile，上方connect的有效位的总数是0或1：0表示直接向输出NoC输出CIMFinalResult结果；1表示输出到互联NoCInterface（在特殊情况下输出到输出NoC）
//                 2.3.3.4.3、每个Tile，下方connect的有效位的总数是0或1：0表示直接从输入NoC接收输出；1表示从互联NoCInterface得到其它Tile的CIMFinalResult结果
//             2.3.3.5、根据2个互联NoCInterface的router信息的，组成2bit systolic信号 确定发送方式
//                 2.3.3.5.1、connect从systolic信号按位与形成communIn信号(第0bit）、communOut信号(第1bit)
//                 2.3.3.5.2、communIn信号有效，与下方Tile之间以systolic方式通信，否则以累加方式通信
//                 2.3.3.5.3、communOut信号有效，与下方Tile之间以systolic方式通信，否则以累加方式通信
//         2.3.4、根据connect信号确定数据流向
//             2.3.4.1、与前级握手时：
//                 connect[0]=0：
//                     Tile内的CIMFSMResult(直接视为CIMFinalResult)数据有效，则根据connect[1]信号决定是否向互联NoC Interface或输出NoC Interface输出
//                 connect[0]=1：
//                     互联NoC与CIMFSMResult均有效后，累加得到CIMFinalResult(并回握下级互联NoC)
//             2.3.4.2、与后级握手时：
//                 connect[1]=0：
//                     CIMFinalResult与输出NoC Interface进行输出握手
//                 connect[1]=1：
//                     CIMFinalResult与上级互联NoC Interface模块进行输出握手
//             2.3.4.3、例外情况
//                 当计数与前级Tile握手总数与配置寄存器的信息(kernelSize)相等时，若Tile内的配置寄存器的工作状态信息为0且(Tile的上级互联NoC Interface模块为systolic模式或不存在)，则将CIMFinalResult握手输出到输出NoC Interface
//     2.4、实现与外部全局总线的数据交互协议
//  3、约束：
//     3.1、inputBandWidth、outputBandWidth、WeightBandWidth必须为2的幂次，否则报错
//
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-03-31 |   陈挺然  |   version1  |   初始版本                 //
// 2024-07-17 |   陈挺然  |   version2  |   输出Noc的带宽降低到colSize，cimFinalResult通过一次握手传输两组数据完成              //
// 2025-08-15 |   陈挺然  |   version3  |   kernelSize=k-1              //
//////////////////////////////////////////////////////////////////////////////

class Tile(
  val tileId: Int          // 当前Tile的本名ID号
) extends Module {
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
  val kernelSizeWidth = log2Ceil(Config.maxKernelSize)
  val workModeWidth = log2Ceil(Config.maxWorkMode)
  val remainWidth = configDataWidth-kernelSizeWidth-workModeWidth
  
  // 计算TileID位宽
  val tileIdWidth = Config.idWidth
  val tileIdUInt = tileId.U(tileIdWidth.W)

  // IO定义
  val io = IO(new Bundle {
    // pingpong 标志
    val pingpong = Input(Bool())
    // inputId
    val inputId = Output(UInt(tileIdWidth.W))
    
    // 输入NoC接口
    val inputNoc = Flipped(Decoupled(new Bundle { // ready信号为高电平有效，表示Tile可以接收输入数据
      val data = Vec(rowSize, SInt(dataWidth.W))
      val writeId = UInt(tileIdWidth.W)
      val writeIdNext = UInt(tileIdWidth.W)
      val count = UInt(8.W)
      val inputMode = UInt(8.W)
      val cout = UInt(log2Ceil(Config.maxPixelParallel).W)  // 添加cout信号域
      val kernelRow = UInt(log2Ceil(Config.maxKernelBlockK).W)  // 添加kernelRow信号域
      val remain = UInt(8.W)
    }))

    // 输出NoC接口
    val outputNoc = Decoupled(new Bundle {
      val data = Vec(colSize, SInt((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W))
      val featureMapLine = UInt(tileIdWidth.W) // 新增
      val count = UInt(8.W)
      val cout = UInt(log2Ceil(Config.maxPixelParallel).W)  // 添加cout信号域
      val kernelRow = UInt(log2Ceil(Config.maxKernelBlockK).W)  // 添加kernelRow信号域
      val remain = UInt(16.W)
    })

    // 配置总线接口
    val configBus = new Bundle {
      val data = Input(UInt(configDataWidth.W))
      val addr = Input(UInt(Config.configAddrWidth.W))
      val en = Input(Bool())
    }

    // 权重总线接口
    val weightBus = new Bundle {
      val data = Input(UInt(weightBandWidth.W))
      val tileId = Input(UInt(tileIdWidth.W))
      val addr = Input(UInt(log2Ceil(colSize * rowSize).W))
      val en = Input(Bool())
    }

    // 互联NoC接口
    val nocUp = new Bundle {
      val valid = Output(Bool())
      val ready = Input(Bool())
      val data = Output(Vec(colSize*2, SInt((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W)))
      val router = Input(UInt(4.W))
    }

    val nocDown = new Bundle {
      val valid = Input(Bool())
      val ready = Output(Bool())
      val data = Input(Vec(colSize*2, SInt((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W)))
      val router = Input(UInt(4.W))
    }
  })

  // 配置寄存器 - 使用 Reg 存储，默认配置：k=3(input为k-1=2), inputId=0, workMode=1, featureMapLine=tileIdUInt, remain=0
  private val defaultKernelSize = 2.U(kernelSizeWidth.W) // k-1
  private val defaultInputId = 0.U(tileIdWidth.W)
  private val defaultWorkMode = 1.U(workModeWidth.W)
  private val defaultFeatureMapLine = tileIdUInt
  private val usedWidth = kernelSizeWidth + tileIdWidth + workModeWidth + tileIdWidth
  private val defaultRemain = 0.U((configDataWidth - usedWidth).W)
  private val defaultConfigPacked = Cat(defaultRemain, defaultFeatureMapLine, defaultWorkMode, defaultInputId, defaultKernelSize)
  val configReg = RegInit(defaultConfigPacked)
  when(io.configBus.en && (io.configBus.addr === tileIdUInt)) {
    configReg := io.configBus.data
  }
  // kernelSize信息域实际表达的是卷积核k值-1，直接使用即可
  val kernelSize = configReg(kernelSizeWidth-1, 0)
  val inputId = configReg(kernelSizeWidth + tileIdWidth-1, kernelSizeWidth)
  val workMode = configReg(workModeWidth + kernelSizeWidth + tileIdWidth-1, kernelSizeWidth + tileIdWidth)
  val featureMapLine = configReg(workModeWidth + kernelSizeWidth + tileIdWidth + tileIdWidth-1, workModeWidth + kernelSizeWidth + tileIdWidth)
  val remain = configReg(configDataWidth-1, workModeWidth + kernelSizeWidth + tileIdWidth + tileIdWidth)

  // CIMCore实例化
  val cimCore = Module(new CIMCore(
    rowSize = rowSize,
    colSize = colSize,
    dataWidth = dataWidth,
    outputWidth = outputWidth,
    weightBandWidth = weightBandWidth,
    pipeline = pipeline,
    tLatency = tLatency
  ))

  // 移位相加寄存器
  val shiftAddReg = RegInit(VecInit(Seq.fill(colSize*2)(0.S((outputWidth + log2Ceil(tileSize)+log2Ceil(colSize)).W))))
  val shiftAddCounter = RegInit(0.U(8.W))

  // CIMFSMResult寄存器
  val cimFsmResult = RegInit(VecInit(Seq.fill(2*colSize)(0.S((outputWidth + log2Ceil(tileSize)+log2Ceil(colSize)).W))))
  
  // CIMFinalResult寄存器
  val cimFinalResult = RegInit(VecInit(Seq.fill(2*colSize)(0.S((outputWidth + log2Ceil(tileSize)+log2Ceil(colSize)).W))))

  // 互联NoC控制信号
  val deliver = Cat( io.nocUp.router(3) , io.nocDown.router(3) )
  val systolic = Cat( io.nocUp.router(2) , io.nocDown.router(2) )
  val remainDown = io.nocDown.router(1,0)
  val remainUp = io.nocUp.router(1,0)
  val connect = deliver
  val communIn = connect(0) & systolic(0) // 下方有互联且为systolic模式
  val communOut = connect(1) & systolic(1) // 上方有互联且为systolic模式
  

  // 移位相加状态机
  val sShiftIdle :: sShiftCompute :: sShiftDone :: Nil = Enum(3)
  val shiftState = RegInit(sShiftIdle)

  // NoC输出状态机
  val sNocIdle :: sNocWait :: sNocOutputFirst :: sNocOutputSecond :: Nil = Enum(4)
  val nocState = RegInit(sNocIdle)

  // 初始化输出信号
  io.inputId := inputId
  
  val nocUpValidReg = RegInit(false.B)
  io.nocUp.valid := nocUpValidReg
  io.nocUp.data := VecInit(Seq.fill(2*colSize)(0.S((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W)))

  io.nocDown.ready := false.B

  val outputNocValidReg = RegInit(false.B)
  io.outputNoc.valid := outputNocValidReg
  io.outputNoc.bits.data := VecInit(Seq.fill(colSize)(0.S((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W)))
  io.outputNoc.bits.featureMapLine := featureMapLine
  io.outputNoc.bits.count := 0.U
  io.outputNoc.bits.remain := 0.U
  io.outputNoc.bits.cout := 0.U
  io.outputNoc.bits.kernelRow := 0.U

  // 初始化CIMCore接口信号
  cimCore.io.writeWeightEnable := false.B
  cimCore.io.writeWeightData := 0.U(weightBandWidth.W)
  cimCore.io.writeWeightAddress := 0.U(log2Ceil(colSize * rowSize).W)
  cimCore.io.pingpong := io.pingpong

  // 添加FIFO用于传递cout信号
  val fifoDepth = Config.pipeline + 1
  val coutFifo = Module(new Queue(UInt(log2Ceil(Config.maxPixelParallel).W), fifoDepth))
  coutFifo.io.enq.bits := io.inputNoc.bits.cout
  coutFifo.io.enq.valid := io.inputNoc.fire && (io.inputNoc.bits.writeId === inputId)
  
  // 添加FIFO用于传递kernelRow信号
  val kernelRowFifo = Module(new Queue(UInt(log2Ceil(Config.maxKernelBlockK).W), fifoDepth))
  kernelRowFifo.io.enq.bits := io.inputNoc.bits.kernelRow
  kernelRowFifo.io.enq.valid := io.inputNoc.fire && (io.inputNoc.bits.writeId === inputId)

  // 添加FIFO用于传递inputMode信号
  val inputModeFifo = Module(new Queue(UInt(1.W), fifoDepth)) // inputMode位宽为8位
  inputModeFifo.io.enq.bits := io.inputNoc.bits.inputMode =/= 0.U // 当inputMode不为0时，inputModeFlag有效
  inputModeFifo.io.enq.valid := io.inputNoc.fire && (io.inputNoc.bits.writeId === inputId)

  // 当cimCore.vector.fire时从FIFO取出数据
  val coutShiftedReg = RegInit(0.U(log2Ceil(Config.maxPixelParallel).W))
  val kernelRowShiftedReg = RegInit(0.U(log2Ceil(Config.maxKernelBlockK).W))
  val inputModeShiftedReg = RegInit(0.U(1.W))
  
  when(cimCore.io.vectorOut.fire) {
    coutShiftedReg := coutFifo.io.deq.bits
    kernelRowShiftedReg := kernelRowFifo.io.deq.bits
    inputModeShiftedReg := inputModeFifo.io.deq.bits
    coutFifo.io.deq.ready := true.B
    kernelRowFifo.io.deq.ready := true.B
    inputModeFifo.io.deq.ready := true.B
  }.otherwise {
    coutFifo.io.deq.ready := false.B
    kernelRowFifo.io.deq.ready := false.B
    inputModeFifo.io.deq.ready := false.B
  }
  
  // cout状态寄存器
  val coutDoneReg = RegInit(0.U(log2Ceil(Config.maxPixelParallel).W))
  val coutNocReg = RegInit(0.U(log2Ceil(Config.maxPixelParallel).W))
  
  // kernelRow状态寄存器
  val kernelRowDoneReg = RegInit(0.U(log2Ceil(Config.maxKernelBlockK).W))
  val kernelRowNocReg = RegInit(0.U(log2Ceil(Config.maxKernelBlockK).W))

  // inputMode状态寄存器
  val inputModeDoneReg = RegInit(0.U(1.W))
  val inputModeNocReg = RegInit(0.U(1.W))
  
  // 当输出状态机空闲时更新Noc寄存器
  // when(nocState === sNocWait) {
  //   coutNocReg := coutDoneReg
  //   kernelRowNocReg := kernelRowDoneReg
  //   inputModeNocReg := inputModeDoneReg
  // }
  
  // 连接outputNoc的信号
  io.outputNoc.bits.cout := coutNocReg
  io.outputNoc.bits.kernelRow := kernelRowNocReg
  
  // 移位相加状态机逻辑
  switch(shiftState) {
    is(sShiftIdle) {      
      when(cimCore.io.vectorOut.valid) {
        when( kernelSize === 0.U && workMode === 0.U) { // PW卷积
          // k=1的卷积，不需要移位相加
          // 初始化移位相加寄存器
          for (i <- 0 until colSize) {
            shiftAddReg(i) := cimCore.io.vectorOut.bits(i)
          }
          // 改变移位累加计数器
          shiftAddCounter := 1.U
          // 更新状态寄存器
          shiftState := sShiftDone
        }.otherwise { 
          // k>=2的卷积，需要移位相加
          // 初始化移位相加寄存器
          for (i <- 0 until colSize) {
            shiftAddReg(i) := cimCore.io.vectorOut.bits(i)
          }
          // 改变移位累加计数器
          shiftAddCounter := 1.U
          // 更新状态寄存器
          shiftState := sShiftCompute
        }
      }
    }

    is(sShiftCompute) {
      when(shiftAddCounter < kernelSize) {
        when(cimCore.io.vectorOut.valid) {
          // 执行移位相加
          for (i <- 0 until colSize) {
            val index = i.U + shiftAddCounter
            shiftAddReg(index) := shiftAddReg(index) + cimCore.io.vectorOut.bits(i)
          }
          
          shiftAddCounter := shiftAddCounter + 1.U
        }
      }.otherwise { // 最后一次移位相加
          when(cimCore.io.vectorOut.valid) {
          // 执行移位相加
          for (i <- 0 until colSize) {
            val index = i.U + shiftAddCounter
            shiftAddReg(index) := shiftAddReg(index) + cimCore.io.vectorOut.bits(i)
          }
          // 更新状态寄存器
          shiftState := sShiftDone
        }
      }
    }

    is(sShiftDone) {
      when(nocState === sNocIdle) {
        shiftState := sShiftIdle
        shiftAddCounter := 0.U
        // 移位相加完成，更新结果
        for (i <- 0 until 2*colSize) {
          cimFsmResult(i) := shiftAddReg(i)
          shiftAddReg(i) := 0.S((outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)).W)
        }  
        // 当移位完成时更新状态寄存器
        coutNocReg := coutShiftedReg
        kernelRowNocReg := kernelRowShiftedReg
        inputModeNocReg := inputModeShiftedReg
      }.otherwise {
        shiftState := sShiftDone  // 保持当前状态直到NoC状态机就绪
      }
    }
  }

  // 输出NoC第一组数据传输完成状态
  val outputNocFirstTransfered = RegInit(false.B)
  val systolicFlushed = RegInit(false.B)

  // NoC输出状态机逻辑
  switch(nocState) {
    is(sNocIdle) {
      // 当shift状态机结束时，切换到sNocWait状态
      when(shiftState === sShiftDone) {
        nocState := sNocWait
      }.otherwise {
        nocState := sNocIdle
      }
      nocUpValidReg := false.B
      outputNocValidReg := false.B
      systolicFlushed := false.B
      outputNocFirstTransfered := false.B
    }

    is(sNocWait) {        // 当移位完成时更新状态寄存器
      // coutDoneReg := coutShiftedReg
      // kernelRowDoneReg := kernelRowShiftedReg
      // inputModeDoneReg := inputModeShiftedReg
      when(connect(0)) { // 下方有互联
        when(io.nocDown.valid) {
          // 与下级互联NoC模块内数据相加
          for (i <- 0 until 2*colSize) {
            cimFinalResult(i) := cimFsmResult(i) + io.nocDown.data(i)
          }
          io.nocDown.ready := true.B
          nocState := sNocOutputFirst
          // validState预置位
          when(connect(1)) {  // 上方有互联   
            nocUpValidReg := true.B // 使valid随nocState一并切换，降低由于握手导致的延时
          }
          when(!connect(1) || (connect(1) && systolic(1) && inputModeNocReg=/=0.U)) { // 提前识别sNocOutputFirst状态的工作模式
            outputNocValidReg := true.B // 使valid随nocState一并切换，降低由于握手导致的延时
          }
        }
      }.otherwise { // 下方无互联
        cimFinalResult := cimFsmResult
        nocState := sNocOutputFirst
        // validState预置位
        when(connect(1)) {  // 上方有互联   
          nocUpValidReg := true.B // 使valid随nocState一并切换，降低由于握手导致的延时
        }
        when(!connect(1) || (connect(1) && systolic(1) && inputModeNocReg=/=0.U)) { // 提前识别sNocOutputFirst状态的工作模式
          outputNocValidReg := true.B // 使valid随nocState一并切换，降低由于握手导致的延时
        }
      }
    }

    is(sNocOutputFirst) {
      // 与NocUp连接关系			
      // 无互联无systolic	无互联有systolic	有互联无systolic	有互联有systolic
      // 非FLOOD	inputMode为0	out	out	inter	inter
      // FLOOD	inputMode不为0	out	out	inter	out

      io.nocDown.ready := false.B
      when(connect(1) && !systolic(1) || connect(1) && systolic(1) && (inputModeNocReg===0.U)) { // 上方有add模式互联或者互联模式systlic但inputModeFlag为0 
        // 结果传输给上级互联Noc模块
        when(io.nocUp.ready && io.nocUp.valid) {
          nocState := sNocIdle // 传输完成，切换到空闲状态
          nocUpValidReg := false.B // 拉低握手信号，避免由于状态机卡顿导致的重复传输
        }
        io.nocUp.data := cimFinalResult
      }.elsewhen(!connect(1)) { // 上方无互联
        // 输出到输出NoC
        io.outputNoc.bits.data := VecInit((0 until colSize).map(i => cimFinalResult(i)))
        io.outputNoc.bits.featureMapLine := featureMapLine // 赋值
        io.outputNoc.bits.count := 0.U
        io.outputNoc.bits.remain := remain
        when(io.outputNoc.valid && io.outputNoc.ready) { // 第一次传输完成
          when(kernelSize === 0.U) { // k=1 时直接进入空闲态
            nocState := sNocIdle
            outputNocValidReg := false.B
          }.otherwise {
            nocState := sNocOutputSecond // 默认切换到第二次传输
          }
          // k>1 时，该次握手要传输两组数据，不拉低握手信号
        }
      }.otherwise { // 上方有systolic互联且inputModeFlag为1
        // 复位脉冲阵列（清空InterNoc内寄存的数据）
        io.nocUp.data := VecInit(Seq.fill(2*colSize)(0.S((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W)))
        when(io.nocUp.ready && io.nocUp.valid) { // 与上级互联Noc模块握手成功
          systolicFlushed := true.B //
          nocUpValidReg := false.B // 拉低握手信号，避免由于状态机卡顿导致的重复传输
        }
        // 输出到输出NoC
        io.outputNoc.bits.data := VecInit((0 until colSize).map(i => cimFinalResult(i)))
        io.outputNoc.bits.featureMapLine := featureMapLine // 赋值
        io.outputNoc.bits.count := 0.U
        io.outputNoc.bits.remain := remain
        when(io.outputNoc.valid && io.outputNoc.ready) { // 第一次传输完成，切换到第二次传输
          outputNocFirstTransfered := true.B
          // 由于该次握手要传输两组数据，不拉低握手信号
        }
        // 当脉冲结构复位且该次握手第一组数据输出均完成，切换到该握手第二组数据的传输
        when(systolicFlushed && outputNocFirstTransfered) { // 脉冲结构(InterNoc内缓存数据)复位完成
          when(kernelSize === 0.U) { // k=1 时直接进入空闲态
            nocState := sNocIdle
            outputNocValidReg := false.B
            systolicFlushed := false.B
            outputNocFirstTransfered := false.B
          }.otherwise {
            nocState := sNocOutputSecond // k>1 正常进入第二次传输
            systolicFlushed := false.B
            outputNocFirstTransfered := false.B
          }
        }
      }
    }

    is(sNocOutputSecond) {
      io.nocDown.ready := false.B
      when(connect(1) && !systolic(1) || connect(1) && systolic(1) && (inputModeNocReg===0.U)) { // 上方有add模式互联或者互联模式systolic但inputModeFlag为0 
        // 空逻辑
      }.otherwise { // 上方无互联或互联为systolic模式但inputModeFlag为1
          // 输出到输出NoC
        io.outputNoc.valid := true.B
        io.outputNoc.bits.data := VecInit((0 until colSize).map(i => cimFinalResult(i + colSize)))
        io.outputNoc.bits.featureMapLine := featureMapLine // 赋值
        io.outputNoc.bits.count := 1.U
        io.outputNoc.bits.remain := remain
        when(io.outputNoc.valid && io.outputNoc.ready) { // 输出NoC接口准备好后，清空输出信号
          // 切换到空闲状态
          nocState := sNocIdle
          outputNocValidReg := false.B // 拉低握手valid信号，降低握手延时
        }
      }
    }
  }

  // 权重总线处理
  when(io.weightBus.en && (io.weightBus.tileId === tileIdUInt)) {
    cimCore.io.writeWeightEnable := true.B
    cimCore.io.writeWeightData := io.weightBus.data
    cimCore.io.writeWeightAddress := io.weightBus.addr
  }

  // CIMCore输入连接
  cimCore.io.vectorIn.valid := io.inputNoc.valid && (io.inputNoc.bits.writeId === inputId)
  cimCore.io.vectorIn.bits := io.inputNoc.bits.data
  io.inputNoc.ready := cimCore.io.vectorIn.ready
  
  // CIMCore输出连接
  cimCore.io.vectorOut.ready := shiftState =/= sShiftDone
}
