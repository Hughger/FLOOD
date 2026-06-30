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
// Description: 多核架构的完整封装结构，用于：
    // 1、维护整个多核架构的数据流及工作状态
    // 2、对多核架构内各个Tile的输出进行仲裁
    // 3、实现核间路由NoC协议的数据传输部分
    // 4、实现与外部全局总线的数据交互协议                       
    // 5、通过配置总线完成对多核架构内各个Tile的配置
    // 6、通过权重总线完成对多核架构内各个Tile的权重更新
    // 7、通过输入NoC完成对多核架构内各个Tile的数据输入
    // 8、通过输出NoC完成对多核架构内各个Tile的数据输出
    // 9、通过配置interNoc完成整个多核架构的工作状态重构（特征图Block输入通道、特征图Block行）
// Modification History:                             
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-05-13 |   陈挺然    |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.cluster

import chisel3._
import chisel3.util._
import scala.math._
import FLOOD_Accelerator.core.Tile
import FLOOD_Accelerator.core.Config
import FLOOD_Accelerator.noc.InterNoC
import FLOOD_Accelerator.sram.pingpongBuffer
import FLOOD_Accelerator.sram.vector

class Cluster extends Module {
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

  // 计算位宽
  val tileIdWidth = Config.idWidth

  // IO定义
  val io = IO(new Bundle {
    // 乒乓控制信号
    val pingpong = Input(Bool())

    // 输入NoC接口
    val inputNoc = Flipped(Decoupled(new Bundle {
      val data = Vec(rowSize, SInt(dataWidth.W))
      val writeId = UInt(tileIdWidth.W)
      val writeIdNext = UInt(tileIdWidth.W)
      val count = UInt(8.W)
      val inputMode = UInt(8.W)
      val cout = UInt(log2Ceil(Config.maxPixelParallel).W)
      val kernelRow = UInt(log2Ceil(Config.maxKernelBlockK).W)  // 添加kernelRow信号域
      val remain = UInt(8.W)
    }))
    val inputNocReady = Output(Bool())

    // 输出NoC接口
    val outputNoc = Decoupled(new Bundle {
      val data = Vec(colSize, SInt((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W))
      val featureMapLine = UInt(tileIdWidth.W)
      val count = UInt(8.W)
      val cout = UInt(log2Ceil(Config.maxPixelParallel).W)
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
  })

  // 实例化Tile模块
  val tiles = Seq.tabulate(tileSize) { i =>
    Module(new Tile(tileId = Config.tileConfIdStart + i))
  }

  // 实例化InterNoC模块
  val interNocs = Seq.tabulate(tileSize-1) { i =>
    Module(new InterNoC(tileId = Config.nocConfIdStart + i))
  }

  // 连接乒乓控制信号
  tiles.foreach(_.io.pingpong := io.pingpong)
  interNocs.foreach(_.io.pingpong := io.pingpong)

  // 连接输入NoC
  tiles.foreach { tile =>
    tile.io.inputNoc.valid := io.inputNoc.valid
    tile.io.inputNoc.bits := io.inputNoc.bits
  }
  
  // 输入NoC的ready信号由inputId与inputNoC的Tile的ready信号共同决定
  // io.inputNoc.ready := tiles.map(tile => tile.io.inputNoc.ready && (tile.io.inputId === io.inputNoc.bits.writeId)).reduce(_ || _)

  io.inputNoc.ready := tiles.map { tile =>
    Mux(tile.io.inputId === io.inputNoc.bits.writeIdNext, 
        tile.io.inputNoc.ready, 
        true.B)
  }.reduce(_ && _)

  io.inputNocReady := tiles.map{tile => 
    Mux(tile.io.inputId === io.inputNoc.bits.writeId, 
        tile.io.inputNoc.ready, 
        true.B)
  }.reduce(_ && _)

  // 连接输出NoC
  val outputArbiter = Module(new RRArbiter(
    new Bundle {
      val data = Vec(colSize, SInt((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W))
      val featureMapLine = UInt(tileIdWidth.W)
      val count = UInt(8.W)
      val cout = UInt(log2Ceil(Config.maxPixelParallel).W)
      val kernelRow = UInt(log2Ceil(Config.maxKernelBlockK).W)  // 添加kernelRow信号域
      val remain = UInt(16.W)
    },
    tileSize
  ))
  
  // 连接所有Tile的输出到Arbiter
  tiles.zipWithIndex.foreach { case (tile, i) =>
    outputArbiter.io.in(i).valid := tile.io.outputNoc.valid
    outputArbiter.io.in(i).bits := tile.io.outputNoc.bits
    tile.io.outputNoc.ready := outputArbiter.io.in(i).ready
  } // 确保Tile0的优先级最高，Tile1其次，依次类推
  
  // 连接Arbiter的输出到Cluster的输出NoC
  io.outputNoc.valid := outputArbiter.io.out.valid
  io.outputNoc.bits := outputArbiter.io.out.bits
  outputArbiter.io.out.ready := io.outputNoc.ready

  // 连接配置总线
  tiles.foreach { tile =>
    tile.io.configBus := io.configBus
  }
  interNocs.foreach { noc =>
    noc.io.configBus := io.configBus
  }

  // 连接权重总线
  tiles.foreach { tile =>
    tile.io.weightBus := io.weightBus
  }

  // 连接Tile和InterNoC
  for (i <- 0 until tileSize-1) {
    // 连接下方Tile和InterNoC
    tiles(i).io.nocDown <> interNocs(i).io.nocUp

    // 连接上方Tile和InterNoC
    tiles(i+1).io.nocUp <> interNocs(i).io.nocDown
  }

  // 最下方Tile的nocDown接口置为无效
  tiles(tileSize-1).io.nocDown.valid := true.B
  tiles(tileSize-1).io.nocDown.data := VecInit(Seq.fill(2*colSize)(0.S((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W)))
  tiles(tileSize-1).io.nocDown.router := 0.U

  // 最上方Tile的nocUp接口置为无效
  tiles(0).io.nocUp.ready := true.B
  tiles(0).io.nocUp.router := 0.U
}