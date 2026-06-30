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
// Module     : ioclass.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: 全局例化顶层设计，遵循增量设计原理，完成的代码将被另存在各个子文件夹中
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
 
 package FLOOD_Accelerator
 
 import chisel3._
 import chisel3.util._
 import FLOOD_Accelerator.sram
 import FLOOD_Accelerator.core
 import FLOOD_Accelerator.core.Config
 import FLOOD_Accelerator.noc
 import FLOOD_Accelerator.cluster
 import FLOOD_Accelerator.machine
 

 // 生成 Verilog 代码 (Chisel Stage)
//  object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new core.MACTree(size = 64, dataWidth = 8, bandWidth = 128), Array("--target-dir", "generated"))
//  }

// MACTree
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new core.MACTree(), Array("--target-dir", "generated"))
// }

// MACTreeRefine
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new core.MACTreeRefine(), Array("--target-dir", "generated"))
// }

// Vector
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new sram.vector(size = 4, dataWidth = 8, bandWidth = 8), Array("--target-dir", "generated"))
// }

// CIMCore
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new core.CIMCore(weightBandWidth=16, rowSize = 4, colSize = 4, dataWidth = 8, outputWidth = 8, pipeline = 2, tLatency = 1), Array("--target-dir", "generated"))
// }

// Tile
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new core.Tile(tileId = 0), Array("--target-dir", "generated"))
// }

// InterNoC
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new noc.InterNoC(tileId = 0), Array("--target-dir", "generated"))
// }

// Cluster
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new cluster.Cluster, Array("--target-dir", "generated"))
// }

// FSM
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new machine.FSM(FSMId = 16), Array("--target-dir", "generated"))
// }

// OutRouter
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new machine.OutRouter(FSMId = 8), Array("--target-dir", "generated"))
// }

// OutRouterPlane
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new machine.OutRouterPlane(tileId = 2*Config.tileSize), Array("--target-dir", "generated"))
// }

// OutRouterPlanePost
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new machine.OutRouterPlanePost(tileId = 2*Config.tileSize), Array("--target-dir", "generated"))
// }

// MultipleDetector
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new machine.MultipleDetector, Array("--target-dir", "generated"))
// }

// MacMachine
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new machine.MacMachine, Array("--target-dir", "generated"))
// }

// TransSram3D
// object GenerateVerilog extends App {
//   (new chisel3.stage.ChiselStage).emitVerilog(new sram.TransSram3D(pingpongInherit = false, blockLength = Config.tileSize, blockWidth = Config.colSize, blockChannel = Config.rowSize), Array("--target-dir", "generated"))
// }

// MacMachineWrapper
object GenerateVerilog extends App {
  (new chisel3.stage.ChiselStage).emitVerilog(new machine.MacMachineWrapper, Array("--target-dir", "generated"))
}
