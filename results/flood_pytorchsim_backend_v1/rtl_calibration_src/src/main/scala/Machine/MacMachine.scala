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
//     1. FSM、Cluster、OutRouter三个模块的合并
//     a. FSM与Cluster模块相连
//         i. 主要为对接inputNoc
//         ii. 共享ConfigBus
//     b. Cluster模块与OutRouter模块相连

// Modification History:                             
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-07-17 |   陈挺然    |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.machine

import chisel3._
import chisel3.util._
import FLOOD_Accelerator.core.Config
import FLOOD_Accelerator.cluster.Cluster
import FLOOD_Accelerator.machine.FSMDualMode
import FLOOD_Accelerator.machine.FSM
import FLOOD_Accelerator.machine.OutRouterPlane

class MacMachine extends Module {
  // 从Config对象获取参数
  val colSize = Config.colSize
  val tileSize = Config.tileSize
  val outputWidth = Config.outputWidth
  val outputBufferDataWidth = Config.outputBufferDataWidth
  val configDataWidth = Config.configDataWidth
  val dataWidth = Config.dataWidth
  val rowSize = Config.rowSize
  val featureMapBandWidth = Config.featureMapBandWidth
  val weightBandWidth = Config.weightBandWidth

  // 计算地址位宽
  val weightAddrWidth = log2Ceil(Config.weightSramLength)
  val outputAddrWidth = log2Ceil(Config.outputSramLength)

  val io = IO(new Bundle {
    // 乒乓标志
    // 新增：分别用于选择Wrapper中 weightSramRead 与 outputSram 的乒乓分支
    val weightPingpong = Output(Bool()) //选择从哪个weightSram读
    val outputPingpong = Output(Bool()) //选择从哪个outputSram读写

    // 配置总线
    val configBus = new Bundle {
      val data = Input(UInt(Config.configDataWidth.W))
      val addr = Input(UInt((Config.configAddrWidth).W))
      val en = Input(Bool())
    }
    // 特征图总线
    val featureMapBus = new Bundle {
      val data = Input(UInt(Config.featureMapBandWidth.W))
      val tileId = Input(UInt((2*log2Ceil(Config.tileSize)).W))
      val addr = Input(UInt(log2Ceil(Config.colSize * Config.rowSize).W))
      val en = Input(Bool())
    }
    // FSM启动/完成
    val start = Flipped(Decoupled(Bool()))
    val FSMdone = Decoupled(Bool())
    val OutRouterdone = Decoupled(Bool())

    // SRAM读接口
    val weightSramRead = new Bundle {
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(weightAddrWidth.W))
      val readData = Input(UInt((rowSize * dataWidth).W))
    }

    // SRAM写接口
    val outputSramWrite = new Bundle {
      val writeEnable = Output(Bool())
      val writeAddress = Output(UInt(outputAddrWidth.W))
      val writeData = Output(UInt((colSize * Config.outputBufferTmpWidth).W))
    }
    
    // SRAM读接口
    val outputSramRead = new Bundle {
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(outputAddrWidth.W))
      val readData = Input(UInt((colSize * Config.outputBufferTmpWidth).W))
    }

    // 输出区域边界（由 OutRouterPlanePost 导出，用于 Wrapper 判断 joint 选通）
    // val outputBufferBias = Output(UInt(outputAddrWidth.W))
    
    // Joint SRAM写接口
    val jointSramWrite = new Bundle {
      val writeEnable = Output(Bool())
      val writeAddress = Output(UInt(log2Ceil(Config.jointSramLength).W))
      val writeData = Output(UInt((colSize * Config.outputBufferTmpWidth).W))
    }
    
    // Joint SRAM读接口
    val jointSramRead = new Bundle {
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(log2Ceil(Config.jointSramLength).W))
      val readData = Input(UInt((colSize * Config.outputBufferTmpWidth).W))
    }
    // 错误信号
    val error = Output(Bool())
  })
  // 全局配置寄存器
  val globalConfigReg = RegInit(0.U(configDataWidth.W))
  when(io.configBus.en && io.configBus.addr === (Config.globalConfId).U) {
    globalConfigReg := io.configBus.data
  }
  val actionMode = globalConfigReg(7, 0)
  // 乒乓控制位：最高位作为全局pingpong，其次两位分别用于weight与output接口的乒乓选择
  val pingpong        = globalConfigReg(configDataWidth-1) // 倒数第一位
  val weightPingpong  = globalConfigReg(configDataWidth-2) // 倒数第二位
  val outputPingpong  = globalConfigReg(configDataWidth-3) // 倒数第三位

  // 乒乓信号向外输出
  io.weightPingpong := weightPingpong
  io.outputPingpong := outputPingpong

  // 实例化
  val fsm = Module(new FSMDualMode)
  val cluster = Module(new Cluster)
  // val outRouter = Module(new OutRouterPlanePost(Config.FSMRouterConfIdStart))
  val outRouter = Module(new OutRouterPlanePost)

  // 乒乓信号：由globalConfigReg的bit[8]提供
  fsm.io.pingpong := pingpong
  cluster.io.pingpong := pingpong
  outRouter.io.pingpong := pingpong

  // 数据流模式信号连接
  fsm.io.dataflowMode := actionMode(0)  // dataFlowMode: false: FLOOD, true: NVDIA

  // 配置总线
  fsm.io.configBus <> io.configBus
  cluster.io.configBus <> io.configBus
  outRouter.io.configBus <> io.configBus
  
  // OutRouterPlanePost 的 actionMode 信号连接
  outRouter.io.actionMode.dataFlowMode := actionMode(0)
  outRouter.io.actionMode.isFinalCinIdx := actionMode(1)
  outRouter.io.actionMode.bnEn := actionMode(2)
  outRouter.io.actionMode.actEn := actionMode(3)
  outRouter.io.actionMode.poolEn := actionMode(4)

  // FSM启动/完成
  fsm.io.start <> io.start

  // FSM-Cluster连接
  cluster.io.inputNoc <> fsm.io.inputNoc
  fsm.io.inputNocReady := cluster.io.inputNocReady

  // Cluster-OutRouter连接
  outRouter.io.outputNoc <> cluster.io.outputNoc
  
  // 特征图SRAM写接口
  cluster.io.weightBus.tileId := io.featureMapBus.tileId
  cluster.io.weightBus.addr := io.featureMapBus.addr
  cluster.io.weightBus.data := io.featureMapBus.data
  cluster.io.weightBus.en := io.featureMapBus.en
  

  // 权重SRAM读接口
  io.weightSramRead.readEnable := fsm.io.weightSramRead.readEnable
  io.weightSramRead.readAddress := fsm.io.weightSramRead.readAddress
  fsm.io.weightSramRead.readData := io.weightSramRead.readData

  // 结果SRAM写接口
  io.outputSramWrite.writeEnable := outRouter.io.outputSramWrite.enable
  io.outputSramWrite.writeAddress := outRouter.io.outputSramWrite.address
  io.outputSramWrite.writeData := outRouter.io.outputSramWrite.data
  
  // 结果SRAM读接口
  io.outputSramRead.readEnable := outRouter.io.outputSramRead.enable
  io.outputSramRead.readAddress := outRouter.io.outputSramRead.address
  outRouter.io.outputSramRead.data := io.outputSramRead.readData

  // 输出区域边界导出
  // 说明：此处直接复用 OutRouter 的边界输出（若 OutRouter 暂未改名为 outputBufferBias，可先接它现有的边界 IO）
  // io.outputBufferBias := outRouter.io.outputjointBias
  
  // Joint SRAM写接口
  io.jointSramWrite.writeEnable := outRouter.io.jointSramWrite.enable
  io.jointSramWrite.writeAddress := outRouter.io.jointSramWrite.address
  io.jointSramWrite.writeData := outRouter.io.jointSramWrite.data
  
  // Joint SRAM读接口
  io.jointSramRead.readEnable := outRouter.io.jointSramRead.enable
  io.jointSramRead.readAddress := outRouter.io.jointSramRead.address
  outRouter.io.jointSramRead.data := io.jointSramRead.readData

  // 2个done信号由FSM和OutRouter分别发起
  io.FSMdone <> fsm.io.done
  io.OutRouterdone <> outRouter.io.done

  // 错误信号
  io.error := fsm.io.error || outRouter.io.error
}

