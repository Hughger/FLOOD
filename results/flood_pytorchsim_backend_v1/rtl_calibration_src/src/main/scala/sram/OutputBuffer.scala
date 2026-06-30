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
// Module     : OutputBuffer.scala                                          //
// Author     : 陈挺然                                                      //
// Email      : 18073369150@buaa.edu.cn                                     //
// Description: 输出缓存管理模块，内部例化3个outputSram和1个jointSram
//   1. 3个outputSram：前2个用作乒乓缓存，第3个用作特殊写入空间和列向拼接读空间
//   2. 1个jointSram：用于边界拼接缓存
//   3. 支持乒乓控制和总线复用
//   4. 第3个outputSram具有特殊的地址映射逻辑
//   5. 新增：AXI read接口用于外部总线读取
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-01-XX |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.sram

import chisel3._
import chisel3.util._
import FLOOD_Accelerator.core.Config

class OutputBuffer(
  val tileId: Int
) extends Module {
  // 从Config获取参数
  val colSize = Config.colSize
  val rowSize = Config.rowSize
  val tileSize = Config.tileSize
  val outputBufferDataWidth = Config.outputBufferDataWidth
  val configDataWidth = Config.configDataWidth
  
  // 计算地址位宽
  val outputAddrWidth = log2Ceil(Config.outputSramLength)
  val jointAddrWidth = log2Ceil(Config.jointSramLength)
  
  // 计算第3个outputSram的地址偏移量
  // 由于地址位宽限制，我们需要调整策略
  // 将地址空间分为两部分：前一半给乒乓outputSram，后一半给第3个outputSram
  val outputSram2Bias = (Config.outputSramLength / 2).U
  
  // IO定义
  val io = IO(new Bundle {
    // 乒乓控制信号（用于前2个outputSram）
    val pingpong = Input(Bool())
    
    // 配置总线（第0bit用于第3个outputSram和jointSram的乒乓控制）
    val configBus = new Bundle {
      val data = Input(UInt(configDataWidth.W))
      val tileId = Input(UInt((2*log2Ceil(Config.tileSize)).W))
    }
    
    // 统一的SRAM接口
    val outputSramWrite = new Bundle {
      val enable = Input(Bool())
      val address = Input(UInt(outputAddrWidth.W))
      val data = Input(Vec(colSize, SInt(outputBufferDataWidth.W)))
    }
    
    val outputSramRead = new Bundle {
      val enable = Input(Bool())
      val address = Input(UInt(outputAddrWidth.W))
      val data = Output(Vec(colSize, SInt(outputBufferDataWidth.W)))
    }
    
    val jointSramWrite = new Bundle {
      val enable = Input(Bool())
      val address = Input(UInt(jointAddrWidth.W))
      val data = Input(Vec(colSize, SInt(outputBufferDataWidth.W)))
    }
    
    val jointSramRead = new Bundle {
      val enable = Input(Bool())
      val address = Input(UInt(jointAddrWidth.W))
      val data = Output(Vec(colSize, SInt(outputBufferDataWidth.W)))
    }
    
    // 新增：统一的AXI read接口
    val axiRead = new Bundle {
      val enable = Input(Bool())
      val address = Input(UInt((outputAddrWidth + jointAddrWidth).W)) // 支持更大的地址范围
      val data = Output(Vec(rowSize, SInt(outputBufferDataWidth.W)))
      val valid = Output(Bool())
    }
  })
  
  // Configuration buffer with workMode support
  val configBuffer = RegInit(0.U(configDataWidth.W))
  when(io.configBus.tileId === tileId.U) {
    configBuffer := io.configBus.data
  }
  val innerPingPong = configBuffer(0)

  // 实例化3个outputSram
  // 前2个用作乒乓缓存
  val outputSram0 = Module(new TransSram3D(
    pingpongInherit = false,
    blockLength = Config.outputSramLength/2,
    blockWidth = colSize,
    blockChannel = rowSize
  ))
  
  val outputSram1 = Module(new TransSram3D(
    pingpongInherit = true,
    blockLength = Config.outputSramLength/2,
    blockWidth = colSize,
    blockChannel = rowSize
  ))
  
  // 第3个用作特殊用途
  val outputSram2 = Module(new TransSram3D(
    pingpongInherit = false,
    blockLength = Config.outputSramLength/2,
    blockWidth = colSize,
    blockChannel = rowSize
  ))
  
  // 实例化jointSram
  val jointSram = Module(new TransSram3D(
    pingpongInherit = false,
    blockLength = Config.jointSramLength,
    blockWidth = colSize,
    blockChannel = rowSize
  ))
  
  // 乒乓控制信号连接
  outputSram0.io.pingpong := io.pingpong
  outputSram1.io.pingpong := io.pingpong
  
  // 第3个outputSram和jointSram使用configBus的第0bit作为乒乓控制
  outputSram2.io.pingpong := innerPingPong
  jointSram.io.pingpong := innerPingPong
  
  // 写入逻辑：根据地址范围选择目标SRAM
  // 写路径：仅根据写地址判定是否路由到第3个outputSram
  val writeIsOutputSram2Addr = io.outputSramWrite.address >= outputSram2Bias
  // 读路径：仅根据读地址判定是否来自第3个outputSram
  val readIsOutputSram2Addr  = io.outputSramRead.address  >= outputSram2Bias
  
  when(!writeIsOutputSram2Addr) {
    when(io.pingpong) {
      // 写入到outputSram1
      outputSram1.io.baseIO.write.enable := io.outputSramWrite.enable
      outputSram1.io.baseIO.write.address := io.outputSramWrite.address
      outputSram1.io.baseIO.write.data := io.outputSramWrite.data
      
      // 禁用outputSram0
      outputSram0.io.baseIO.write.enable := false.B
      outputSram0.io.baseIO.write.address := 0.U
      outputSram0.io.baseIO.write.data := VecInit(Seq.fill(colSize)(0.S(outputBufferDataWidth.W)))
    }.otherwise {
      // 写入到outputSram0
      outputSram0.io.baseIO.write.enable := io.outputSramWrite.enable
      outputSram0.io.baseIO.write.address := io.outputSramWrite.address
      outputSram0.io.baseIO.write.data := io.outputSramWrite.data
      
      // 禁用outputSram1
      outputSram1.io.baseIO.write.enable := false.B
      outputSram1.io.baseIO.write.address := 0.U
      outputSram1.io.baseIO.write.data := VecInit(Seq.fill(colSize)(0.S(outputBufferDataWidth.W)))
    }
  }.otherwise {
    // 禁用乒乓outputSram
    outputSram0.io.baseIO.write.enable := false.B
    outputSram0.io.baseIO.write.address := 0.U
    outputSram0.io.baseIO.write.data := VecInit(Seq.fill(colSize)(0.S(outputBufferDataWidth.W)))
    outputSram1.io.baseIO.write.enable := false.B
    outputSram1.io.baseIO.write.address := 0.U
    outputSram1.io.baseIO.write.data := VecInit(Seq.fill(colSize)(0.S(outputBufferDataWidth.W)))
  }
  
  // 第3个outputSram的写入
  when(writeIsOutputSram2Addr) {
    outputSram2.io.baseIO.write.enable := io.outputSramWrite.enable
    outputSram2.io.baseIO.write.address := io.outputSramWrite.address - outputSram2Bias
    outputSram2.io.baseIO.write.data := io.outputSramWrite.data
  }.otherwise {
    outputSram2.io.baseIO.write.enable := false.B
    outputSram2.io.baseIO.write.address := 0.U
    outputSram2.io.baseIO.write.data := VecInit(Seq.fill(colSize)(0.S(outputBufferDataWidth.W)))
  }
  
  // jointSram的写入
  jointSram.io.baseIO.write.enable := io.jointSramWrite.enable
  jointSram.io.baseIO.write.address := io.jointSramWrite.address
  jointSram.io.baseIO.write.data := io.jointSramWrite.data
  
  // 读取逻辑：根据地址范围选择源SRAM
  val isOutputSram2ReadAddress = readIsOutputSram2Addr
  
  // 乒乓outputSram的读取
  when(!isOutputSram2ReadAddress) {
    when(io.pingpong) {
      // 从outputSram1读取
      outputSram1.io.baseIO.read.enable := io.outputSramRead.enable
      outputSram1.io.baseIO.read.address := io.outputSramRead.address
      
      // 禁用outputSram0
      outputSram0.io.baseIO.read.enable := false.B
      outputSram0.io.baseIO.read.address := 0.U
    }.otherwise {
      // 从outputSram0读取
      outputSram0.io.baseIO.read.enable := io.outputSramRead.enable
      outputSram0.io.baseIO.read.address := io.outputSramRead.address
      
      // 禁用outputSram1
      outputSram1.io.baseIO.read.enable := false.B
      outputSram1.io.baseIO.read.address := 0.U
    }
  }.otherwise {
    // 禁用乒乓outputSram
    outputSram0.io.baseIO.read.enable := false.B
    outputSram0.io.baseIO.read.address := 0.U
    outputSram1.io.baseIO.read.enable := false.B
    outputSram1.io.baseIO.read.address := 0.U
  }
  
  // 第3个outputSram的读取
  when(isOutputSram2ReadAddress) {
    outputSram2.io.baseIO.read.enable := io.outputSramRead.enable
    outputSram2.io.baseIO.read.address := io.outputSramRead.address - outputSram2Bias
  }.otherwise {
    outputSram2.io.baseIO.read.enable := false.B
    outputSram2.io.baseIO.read.address := 0.U
  }
  
  // jointSram的读取
  jointSram.io.baseIO.read.enable := io.jointSramRead.enable
  jointSram.io.baseIO.read.address := io.jointSramRead.address
  
  // 输出数据选择逻辑
  // outputSram读取数据
  val outputSram0Data = outputSram0.io.baseIO.read.data
  val outputSram1Data = outputSram1.io.baseIO.read.data
  val outputSram2Data = outputSram2.io.baseIO.read.data
  
  // 根据地址范围选择输出数据
  io.outputSramRead.data := Mux(isOutputSram2ReadAddress, 
                                outputSram2Data, 
                                Mux(io.pingpong, outputSram1Data, outputSram0Data))
  
  // jointSram读取数据
  io.jointSramRead.data := jointSram.io.baseIO.read.data
  
  // AXI read接口逻辑
  // 根据地址范围选择对应的AXI读取源
  // 地址范围：0 ~ outputSramLength-1: outputSram
  // 地址范围：outputSramLength ~ outputSramLength+jointSramLength-1: jointSram
  
  val isJointSramAddress = io.axiRead.address >= Config.outputSramLength.U
  val isOutputSram2Address = (io.axiRead.address >= outputSram2Bias) && (isJointSramAddress === false.B)
  // 禁用所有SRAM的AXI读取
  outputSram0.io.axiRead.enable := false.B
  outputSram0.io.axiRead.address := 0.U
  outputSram1.io.axiRead.enable := false.B
  outputSram1.io.axiRead.address := 0.U
  outputSram2.io.axiRead.enable := false.B
  outputSram2.io.axiRead.address := 0.U
  jointSram.io.axiRead.enable := false.B
  jointSram.io.axiRead.address := 0.U
  
  // 根据地址范围选择读取源
  when(isJointSramAddress) {
    // 读取jointSram
    jointSram.io.axiRead.enable := io.axiRead.enable
    jointSram.io.axiRead.address := io.axiRead.address - Config.outputSramLength.U
    io.axiRead.data := jointSram.io.axiRead.data
    io.axiRead.valid := jointSram.io.axiRead.valid
  }.otherwise {
    // 读取outputSram
    when(isOutputSram2Address) {
      // 从第3个outputSram读取
      outputSram2.io.axiRead.enable := io.axiRead.enable
      outputSram2.io.axiRead.address := io.axiRead.address - outputSram2Bias
      io.axiRead.data := outputSram2.io.axiRead.data
      io.axiRead.valid := outputSram2.io.axiRead.valid
    }.otherwise {
      // 从乒乓outputSram读取
      when(io.pingpong) {
        // 从outputSram1读取
        outputSram1.io.axiRead.enable := io.axiRead.enable
        outputSram1.io.axiRead.address := io.axiRead.address
        io.axiRead.data := outputSram1.io.axiRead.data
        io.axiRead.valid := outputSram1.io.axiRead.valid
      }.otherwise {
        // 从outputSram0读取
        outputSram0.io.axiRead.enable := io.axiRead.enable
        outputSram0.io.axiRead.address := io.axiRead.address
        io.axiRead.data := outputSram0.io.axiRead.data
        io.axiRead.valid := outputSram0.io.axiRead.valid
      }
    }
  }
  
  // 设置默认的读取模式（可以根据需要调整）
  outputSram0.io.readMode := 0.U
  outputSram1.io.readMode := 0.U
  outputSram2.io.readMode := 0.U
  jointSram.io.readMode := 0.U
} 