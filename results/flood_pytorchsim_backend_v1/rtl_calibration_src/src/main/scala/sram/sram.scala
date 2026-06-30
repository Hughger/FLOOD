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
// Description: 所有的SRAM接口，用于复用与封装管理
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.sram

import chisel3._
import chisel3.util._
import FLOOD_Accelerator.IOBundle


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
// Description: 最基础的一行存储器，向量格式，其可以多次写入，而结果必须一次全部读出
// 约束：
//   a.其最少一次写入，故bandWidth<=dataWidth*size
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
class vector(size: Int, dataWidth: Int, bandWidth: Int) extends Module {
  // 计算地址总线位宽
  require(size * dataWidth / bandWidth >= 1, "写入次数必须大于等于1")
  val addressWidth = log2Ceil(size * dataWidth / bandWidth)

  // 计算数据总线位宽 (读出时一次性读出所有数据)
  val totalDataWidth = size * dataWidth

  val io = IO(new Bundle {
    val writeEnable = Input(Bool())
    val writeAddress = Input(UInt(addressWidth.W))
    val writeData = Input(UInt(bandWidth.W))
    val readEnable = Input(Bool())
    val readData = Output(UInt(totalDataWidth.W))
  })

  // 使用 SyncReadMem 创建存储器
  val memory = SyncReadMem(size * dataWidth / bandWidth, UInt(bandWidth.W))

  // 写入逻辑
  when(io.writeEnable) {
    memory.write(io.writeAddress, io.writeData)
  }

  // 读取逻辑
  when(io.readEnable) {
    io.readData := Cat((0 until size * dataWidth / bandWidth).map(i => memory.read((size * dataWidth / bandWidth - 1 - i).U)))
  }.otherwise {  
    io.readData := 0.U
  }
}


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
// Module     : pinpongbuffer                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description:/1、基于Vector实现的乒乓vector，
// 2、pingpong有效时，vectorA对应在被写入，而VectorB的结果一直被输出 
// 3、pingpong信号无效时相反 
// 4、pingpong共用一套地址映射，共用一套数据In、数据Out，地址总线
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
class pingpongBuffer(size: Int, dataWidth: Int, bandWidth: Int) extends Module {
  val io = IO(new Bundle {
    val writeEnable = Input(Bool()) // 写使能信号
    val writeAddress = Input(UInt(log2Ceil(size * dataWidth / bandWidth).W)) // 写地址信号
    val writeData = Input(UInt(bandWidth.W)) // 写入数据信号
    val readEnable = Input(Bool()) // 读使能信号
    val readData = Output(UInt((size * dataWidth).W)) // 读取数据信号
    val pingpong = Input(Bool()) // 用于区分哪个 vector 在写入，哪个在读出
  })

  // 实例化两个 vector 模块
  val vectorA = Module(new vector(size, dataWidth, bandWidth))
  val vectorB = Module(new vector(size, dataWidth, bandWidth))

  // 连接写信号
  vectorA.io.writeEnable := io.writeEnable & Mux(io.pingpong, true.B, false.B)
  vectorA.io.writeAddress := Mux(io.pingpong, io.writeAddress, 0.U) // 或者其他默认值
  vectorA.io.writeData := Mux(io.pingpong, io.writeData, 0.U) // 或者其他默认值

  vectorB.io.writeEnable := io.writeEnable & Mux(io.pingpong, false.B, true.B)
  vectorB.io.writeAddress := Mux(io.pingpong, 0.U, io.writeAddress) // 或者其他默认值
  vectorB.io.writeData := Mux(io.pingpong, 0.U, io.writeData) // 或者其他默认值


  // 默认情况下，不进行读取
  vectorA.io.readEnable := false.B
  vectorB.io.readEnable := false.B

  // 根据 pingpong 信号切换读写
  when(io.pingpong) {
    // vectorA 写入，vectorB 读取
    vectorB.io.readEnable := io.readEnable //vectorB 读取使能
    io.readData := vectorB.io.readData // vectorB 的结果输出
  }.otherwise {
    // vectorB 写入，vectorA 读取
    vectorA.io.readEnable := io.readEnable //vectorA 读取使能
    io.readData := vectorA.io.readData // vectorA 的结果输出
  }
}