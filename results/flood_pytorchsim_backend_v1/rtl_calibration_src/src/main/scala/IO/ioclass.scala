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
// Description: 所有的IO接口，用于复用与封装管理
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.IOBundle

import chisel3._
import chisel3.util._

class pingpongBufferIO(size: Int, dataWidth: Int, bandWidth: Int) extends Bundle {//SRAM的普世接口，其地址总线会自行计算
    val writeEnable = Input(Bool())
    val writeAddress = Input(UInt(log2Ceil(size * dataWidth / bandWidth).W))
    val writeData = Input(UInt(bandWidth.W))
    val readEnable = Input(Bool())
    val readData = Output(UInt((size * dataWidth).W))
    val pingpong = Input(Bool())
}