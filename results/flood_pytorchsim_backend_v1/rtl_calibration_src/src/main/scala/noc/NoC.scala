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
// Module     : sram.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: CIM core的所有相关类
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-05-13 |   陈挺然    |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
package FLOOD_Accelerator.noc

import chisel3._
import chisel3.util._
import scala.math._
import FLOOD_Accelerator.core.Config
import FLOOD_Accelerator.sram.pingpongBuffer

// Project    : FLOOD_Accelerator                                               //
// Module     : InterNoC.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: 互联NoC的功能及其可重构性,两个Tile之间部署一个（除了头尾）
// 1、宏参数： core内部的Config 对象
// 2、功能：
//     2.1、维护内部的寄存器内容及握手
//         2.1.1、有两个IO，nocUp（给上方Tile）与nocDown（给下方Tile），与Tile的同名IO互为Decouple关系
//     2.2、根据配置寄存器信息决定内部行为
//         2.2.1、配置寄存器包含一个Router信息，（4bits）分别为：
//             2.2.2.1、最高位表示是否发送，deliver=1表示发送，deliver=0表示不发送
//             2.2.2.2、次高位表示发送方式是累加还是systolic, systolic=0表示累加，systolic=1表示systolic
//             2.2.2.3、末2 bits预留,为remain
//         2.2.3、根据deliver与systolic信号，确定互联NoC模块的行为
//             2.2.3.1、deliver=1，systolic=0，则处于累加模式。当nocDown有数据到来时，将数据暂存到cimFinalResultBuffer中,并发送到nocUp(先暂存再发送)
//             2.2.3.2、deliver=1，systolic=1，则处于systolic模式。当nocUp发送完cimFinalResultBuffer中的数据后,当nocDown有数据到来时，将数据暂存到cimFinalResultBuffer中(先发送再暂存)
//             2.2.3.3、deliver=0，则没有连接，对nocDown一直ready有效，对nocUp一直valid有效且data为0
//         2.2.4、配置寄存器同样乒乓
//  3、约束：
//     3.1、无约束
//  4、IO：
//     4.1、nocUp：
//         4.1.1、valid：有效信号
//         4.1.2、ready：就绪信号
//         4.1.3、data：数据
//         4.1.4、router：路由信息
//     4.2、nocDown：
//         4.2.1、valid：有效信号
//         4.2.2、ready：就绪信号
//         4.2.3、data：数据
//         4.2.4、router：路由信息
//     4.3、configBus：
//         4.3.1、data：数据
//         4.3.2、tileId：TileID
//     4.4、Pingpong：
//
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-05-12 |   陈挺然    |   version1  |   初始版本                 //
// 2025-05-12 |   陈挺然    |   version2  |   修改配置总线接口             //
//////////////////////////////////////////////////////////////////////////////
class InterNoC(
  val tileId: Int,
) extends Module {
  // 从Config对象获取参数
  val weightBandWidth = Config.weightBandWidth
  val colSize = Config.colSize
  val rowSize = Config.rowSize
  
  val outputWidth = Config.outputWidth
  val tileSize = Config.tileSize
  val pipeline = Config.pipeline
  val tLatency = Config.tLatency
  val configBusWidth = Config.configDataWidth

  // 计算位宽
  val tileIdWidth = Config.idWidth
  val tileIdUInt = tileId.U(tileIdWidth.W)
  val tmpDataWidth = outputWidth + log2Ceil(tileSize)+log2Ceil(colSize)

  // IO定义
  val io = IO(new Bundle {
    // 上方Tile接口
    val nocUp = new Bundle {
      val valid = Output(Bool())
      val ready = Input(Bool())
      val data = Output(Vec(colSize*2, SInt(tmpDataWidth.W)))
      val router = Output(UInt(4.W))
    }

    // 下方Tile接口
    val nocDown = new Bundle {
      val valid = Input(Bool())
      val ready = Output(Bool())
      val data = Input(Vec(colSize*2, SInt(tmpDataWidth.W)))
      val router = Output(UInt(4.W))
    }

    // 配置总线接口
    val configBus = new Bundle {
      val data = Input(UInt(Config.configDataWidth.W))
      val addr = Input(UInt(Config.configAddrWidth.W))
      val en = Input(Bool())
    }

    // 乒乓控制信号
    val pingpong = Input(Bool())
  })

  // 配置寄存器 - 使用 Reg 存储
  // 默认使能deliver=1且systolic=1（低4位为 1100b），其余位清零
  val configReg = RegInit("b1100".U(Config.configDataWidth.W))
  when(io.configBus.en && (io.configBus.addr === tileIdUInt)) {
    configReg := io.configBus.data
  }
  val router = configReg(3, 0)  // 4位路由信息
  val deliver = router(3)       // 最高位：是否发送
  val systolic = router(2)      // 次高位：发送模式
  val remain = router(1, 0)     // 末两位：预留

  // 默认输出
  io.nocUp.valid := false.B
  io.nocUp.data := VecInit(Seq.fill(2*colSize)(0.S(tmpDataWidth.W)))
  io.nocUp.router := router
  io.nocDown.ready := false.B
  io.nocDown.router := router

  // 数据缓冲区
  val cimFinalResultBuffer = RegInit(VecInit(Seq.fill(2*colSize)(0.S(tmpDataWidth.W))))
  val bufferValid = RegInit(false.B) // 数据缓冲区更新标志信号

  // 组合逻辑处理
  when(deliver === 1.U) { // deliver=1
    when(systolic === 0.U) { // 累加模式，先接收后发送
      // 当nocDown有数据到来时，将数据暂存到buffer中
      when(io.nocDown.valid && !bufferValid) { // 累加模式下，bufferValid 低电平表示接收状态，高电平表示发送状态
        cimFinalResultBuffer := io.nocDown.data
        bufferValid := true.B
        io.nocDown.ready := true.B
        io.nocUp.valid := false.B
      }.elsewhen(bufferValid) {
        // 发送buffer中的数据
        io.nocUp.valid := true.B
        io.nocUp.data := cimFinalResultBuffer
        io.nocDown.ready := false.B
        when(io.nocUp.ready) {
          bufferValid := false.B
        }
      }.otherwise {
        io.nocUp.valid := false.B
        io.nocDown.ready := false.B
      }
    }.otherwise { // systolic模式，先发送后接收
      // 当nocUp发送完buffer中的数据后，才接收新数据
      when(!bufferValid) { // systolic模式下，bufferValid 低电平表示发送状态，高电平表示接收状态
        // 发送buffer中的数据 (初次计算发送0数据)
        io.nocUp.valid := true.B
        io.nocDown.ready := false.B
        io.nocUp.data := cimFinalResultBuffer
        when(io.nocUp.ready) { // 等待上级Tile返回ready信号
          bufferValid := true.B // 切换工作状态从发送到接收
        }
      }.elsewhen(io.nocDown.valid){ // 等待从nocDown中获取数据来覆写中间寄存器
        // 接收新数据
        cimFinalResultBuffer := io.nocDown.data
        bufferValid := false.B // 接收完之后切换会发送状态
        io.nocDown.ready := true.B
      }.otherwise { // 保持等待从nocDown中获取数据
        io.nocUp.valid := false.B
        io.nocDown.ready := false.B
      }
    }
  }.otherwise { // deliver=0，连接断开
    // 保持ready和valid信号
    io.nocDown.ready := true.B
    io.nocUp.valid := true.B
    io.nocUp.data := VecInit(Seq.fill(2*colSize)(0.S(tmpDataWidth.W)))
    bufferValid := false.B
  }
}