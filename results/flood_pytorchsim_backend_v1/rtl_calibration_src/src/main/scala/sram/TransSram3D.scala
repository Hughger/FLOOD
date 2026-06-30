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
// Module     : TransSram3D.scala                                           //
// Author     : 陈挺然                                                      //
// Email      : 18073369150@buaa.edu.cn                                     //
// Description: 3D SRAM传输模块，根据设计图纸实现：
//   1. 模块内部每个SramUnit接口是一个深度为rowSize的sram
//   2. Sram ggroup由colSize个Unit组成
//   3. 由cout个group组成模块内的所有存储资源
//   4. 写入时根据Addr选择具体的sram group，然后对group内所有的unit执行写入
//   5. 读出时支持不同的数据组合方式
//   6. pingpong信号与pingpongInherit不对应时，被AXI读；否则被Plane读
//   7. 新增：baseIO接口用于plane通信，MUX结构用于AXI读数据汇总
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

class TransSram3D(
  val pingpongInherit: Boolean = false,
  val blockLength: Int = Config.tileSize,
  val blockWidth: Int = Config.colSize,
  val blockChannel: Int = Config.rowSize
) extends Module {
  // 从Config获取参数
  val outputBufferDataWidth = Config.outputBufferDataWidth
  val finalWidth = Config.finalWidth
  
  // 计算地址位宽
  val outputAddrWidth = log2Ceil(Config.outputSramLength)
  val jointAddrWidth = log2Ceil(Config.jointSramLength)
  
  // 计算group数量（blockChannel）
  val groupCount = blockChannel
  
  // 计算地址位宽
  val unitAddrWidth = log2Ceil(2*blockLength) // Addr的低位作为SRAM Group内所有Unit的addr
  val groupSelWidth = log2Ceil(blockChannel) // Addr右移后的高位作为SRAM Group的sel
  
  // IO定义
  val io = IO(new Bundle {
    // 乒乓控制信号
    val pingpong = Input(Bool())
    
    // baseIO接口：用于plane通信，包含所有Unit的write/read口
    val baseIO = new Bundle {
      val write = new Bundle {
        val enable = Input(Bool())
        val address = Input(UInt((groupSelWidth + unitAddrWidth).W)) // 完整地址
        val data = Input(Vec(blockWidth, SInt(outputBufferDataWidth.W)))
      }
      val read = new Bundle {
        val enable = Input(Bool())
        val address = Input(UInt((groupSelWidth + unitAddrWidth).W)) // 完整地址
        val data = Output(Vec(blockWidth, SInt(outputBufferDataWidth.W)))
        val valid = Output(Bool())
      }
    }
    
    // AXI读接口（当pingpong不对应pingpongInherit时）
    val axiRead = new Bundle {
      val enable = Input(Bool())
      val address = Input(UInt((groupSelWidth + unitAddrWidth).W)) // 完整地址
      val data = Output(Vec(groupCount, SInt(outputBufferDataWidth.W)))
      val valid = Output(Bool())
    }
    
    // 数据组合模式选择（用于不同的读取组合方式）
    val readMode = Input(UInt(log2Ceil(Config.maxWorkMode).W)) // 00: 读取单个unit, 01: 读取所有unit, 10: 读取指定unit, 11: 读取指定group的所有unit（与Plane read行为一致）
  })
  
  // 内部SRAM单元实例化
  // 创建blockChannel个group，每个group包含blockWidth个unit，每个unit深度为2*blockLength
  val sramGroups = Seq.tabulate(groupCount) { groupIdx =>
    Seq.tabulate(blockWidth) { unitIdx =>
      // 使用Chisel内置的SyncReadMem创建SRAM单元
      SyncReadMem(1 << unitAddrWidth, SInt(outputBufferDataWidth.W))
    }
  }
  
  // 乒乓控制逻辑
  val usePlaneRead = (io.pingpong === pingpongInherit.B)
  val useAxiRead = !usePlaneRead
  
  // baseIO写入逻辑
  // Addr的低log2Ceil(2*blockLength) bit作为SRAM Group内所有Unit的addr
  // Addr右移log2Ceil(2*blockLength) bit后作为SRAM Group的sel
  val unitAddr = io.baseIO.write.address(unitAddrWidth-1, 0)
  val groupSel = io.baseIO.write.address(groupSelWidth + unitAddrWidth - 1, unitAddrWidth)
  
  // 简化的写入逻辑
  // 使用向量化的方法减少连线复杂度
  val writeGroupMask = Wire(Vec(groupCount, Bool()))
  for (groupIdx <- 0 until groupCount) {
    writeGroupMask(groupIdx) := (groupIdx.U === groupSel)
  }
  
  // 为每个group内的所有unit设置相同的控制信号
  for (groupIdx <- 0 until groupCount) {
    val groupUnits = sramGroups(groupIdx)
    val groupWriteEnable = io.baseIO.write.enable && writeGroupMask(groupIdx) && (io.pingpong === pingpongInherit.B)
    
    // 使用for循环设置group内所有unit
    for (unitIdx <- 0 until blockWidth) {
      val unit = groupUnits(unitIdx)
      when(groupWriteEnable) {
        unit.write(unitAddr, io.baseIO.write.data(unitIdx))
      }
    }
  }
  
  // baseIO读取逻辑
  val planeUnitAddr = io.baseIO.read.address(unitAddrWidth-1, 0)
  val planeGroupSel = io.baseIO.read.address(groupSelWidth + unitAddrWidth - 1, unitAddrWidth)
  
  // 简化的Plane读取逻辑
  val planeReadData = Wire(Vec(blockWidth, SInt(outputBufferDataWidth.W)))
  val planeReadValid = Wire(Bool())
  
  // 初始化输出数据
  for (unitIdx <- 0 until blockWidth) {
    planeReadData(unitIdx) := 0.S(outputBufferDataWidth.W)
  }
  
  // 选择正确的group进行读取
  for (groupIdx <- 0 until groupCount) {
    val groupUnits = sramGroups(groupIdx)
    val groupSelected = (groupIdx.U === planeGroupSel)
    val readEnable = io.baseIO.read.enable && groupSelected && usePlaneRead // 恢复usePlaneRead条件
    
    for (unitIdx <- 0 until blockWidth) {
      val unit = groupUnits(unitIdx)
      when(readEnable) {
        planeReadData(unitIdx) := unit.read(planeUnitAddr)
      }
    }
  }
  
  // planeReadValid应该只在pingpong匹配时才有效，并且延迟1个时钟周期
  planeReadValid := RegNext(io.baseIO.read.enable && usePlaneRead, false.B)
  
  // AXI读逻辑：根据readMode决定读取行为
  val axiUnitAddr = io.axiRead.address(unitAddrWidth-1, 0)
  val axiUnitSel = io.axiRead.address(groupSelWidth + unitAddrWidth - 1, unitAddrWidth)
  val axiGroupSel = io.axiRead.address(groupSelWidth + unitAddrWidth - 1, unitAddrWidth)
  
  val axiReadData = Wire(Vec(groupCount, SInt(outputBufferDataWidth.W)))
  val axiReadValid = Wire(Bool())
  
  // 检查readMode是否为全1（Plane read模式）
  val isPlaneReadMode = (io.readMode === ((1 << log2Ceil(Config.maxWorkMode)) - 1).U)
  
  // AXI读取逻辑
  for (groupIdx <- 0 until groupCount) {
    axiReadData(groupIdx) := 0.S(outputBufferDataWidth.W)
    val groupUnits = sramGroups(groupIdx)
    val readEnable = io.axiRead.enable && useAxiRead
    
    when(readEnable) {
      when(isPlaneReadMode) {
        // readMode为全1时：Plane read行为 - 读取指定group的所有unit数据
        // 注意：当readMode为全1时，AXI接口实际上是在模拟Plane read行为
        // 但由于axiReadData的维度是groupCount，我们只能输出一个数据
        // 这里我们选择输出指定group的第一个unit的数据
        val groupSelected = (groupIdx.U === axiGroupSel)
        when(groupSelected) {
          val unit = groupUnits(0) // 选择第一个unit
          axiReadData(groupIdx) := unit.read(axiUnitAddr)
        }
      }.otherwise {
        // readMode不为全1时：原有AXI read行为 - 读取指定unit的所有group数据
        for (unitIdx <- 0 until blockWidth) {
          when(axiUnitSel === unitIdx.U) {
            val unit = groupUnits(unitIdx)
            axiReadData(groupIdx) := unit.read(axiUnitAddr)
          }
        }
      }
    }
  }
  
  // axiReadValid应该只在pingpong不匹配时才有效，并且延迟1个时钟周期
  axiReadValid := RegNext(io.axiRead.enable && useAxiRead, false.B)
  
  // 输出连接
  io.baseIO.read.data := planeReadData
  io.baseIO.read.valid := planeReadValid
  
  io.axiRead.data := axiReadData
  io.axiRead.valid := axiReadValid
} 