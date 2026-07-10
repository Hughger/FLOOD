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
// Module     : DynamicTruncateData.scala                                  //
// Author     : 陈挺然                                                      //
// Email      : 18073369150@buaa.edu.cn                                     //
// Description: 动态截位数据模块，支持通过寄存器值动态控制截位位数            //
// • 功能特性：                                                             //
//   • 支持算术右移 + 四舍五入的截位操作                                    //
//   • 支持饱和处理，防止数据溢出                                           //
//   • 支持使能控制，可动态开启/关闭截位功能                                //
//   • 支持向量化处理，一次处理多个数据元素                                 //
//   • 截位位数可通过寄存器动态配置                                         //
// • 应用场景：                                                             //
//   • 神经网络硬件加速器中的量化操作                                       //
//   • 高精度到低精度的数据转换                                             //
//   • 可重构MAC阵列中的动态精度控制                                        //
// • 模块类型：                                                             //
//   • DynamicTruncateData: 通用动态截位模块                               //
//   • OutRouterTruncateData: OutRouter专用版本                            //
//   • ConfigurableTruncateData: 可配置位宽版本                            //
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-09-14 |   陈挺然  |   version1  |   初始版本，支持动态截位控制      //
// 2025-09-14 |   陈挺然  |   version2  |   移动到tools包，重构包结构      //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.tools

import chisel3._
import chisel3.util._
import FLOOD_Accelerator.core.Config

/**
 * 动态截位数据模块
 * 支持通过寄存器值动态控制截位位数
 * 
 * 使用场景：用于累加完成结果向outputBuffer的写入
 * - 输出维度与位宽与输入一致
 * - outputWidth表示只有低outputWidth位有效，其余位置零
 * 
 * @param inputWidth 输入数据位宽
 * @param outputWidth 有效位宽（只有低outputWidth位有效）
 * @param vecSize 向量大小
 * @param truncateBitsWidth 截位位数寄存器的位宽
 */
class DynamicTruncateData(
  inputWidth: Int,
  outputWidth: Int,
  vecSize: Int,
  truncateBitsWidth: Int = 8
) extends Module {
  
  val io = IO(new Bundle {
    // 输入数据
    val inputData = Input(Vec(vecSize, SInt(inputWidth.W)))
    // 截位位数控制（寄存器值）
    val truncateBits = Input(UInt(truncateBitsWidth.W))
    // 使能控制：有效时执行移位与截位，无效时直通
    val en = Input(Bool())
    // 输出数据（维度与位宽与输入一致，只有低outputWidth位有效）
    val outputData = Output(Vec(vecSize, SInt(inputWidth.W)))
  })
  
  // 截位逻辑 - 输出维度与位宽与输入一致，只有低outputWidth位有效
  for (i <- 0 until vecSize) {
    val inputValue = io.inputData(i)
    val truncateBits = io.truncateBits
    
    // 计算截位后的值（位宽与输入一致）
    val truncatedValue = Wire(SInt((inputWidth+1).W)) // 预留移位避免溢出
    // 缺省赋值：符号扩展输入，避免未完全初始化（用 Cat + Fill 做标准符号扩展）
    val signBit = inputValue.asUInt(inputWidth-1)
    val extended = Cat(Fill(1, signBit), inputValue.asUInt).asSInt
    truncatedValue := extended
    
    // 计算有效位宽的最大值和最小值
    val maxValue = (1 << (outputWidth - 1)) - 1  // 正数最大值
    val minValue = -(1 << (outputWidth - 1))     // 负数最小值
    
    when(io.en) {
      when(truncateBits > 0.U) {
        // 算术右移
        val shifted = inputValue >> truncateBits
        // 检查被截掉的最低位（第truncateBits-1位）
        val shouldRound = inputValue.asUInt(truncateBits - 1.U)
        // 四舍五入：如果被截掉的最低位是1，则加1
        val rounded = shifted + Mux(shouldRound, 1.S, 0.S)
        
        // 对截位结果进行饱和处理，确保只有低outputWidth位有效
        when(rounded > maxValue.S) {
          // 饱和到最大值，其余位置零
          truncatedValue := maxValue.S
        }.elsewhen(rounded < minValue.S) {
          // 饱和到最小值，其余位置零
          truncatedValue := minValue.S
        }.otherwise {
          // 正常截位结果，其余位置零
          truncatedValue := rounded
        }
      }.otherwise {
        // 不截位，但进行饱和处理，确保只有低outputWidth位有效
        when(inputValue > maxValue.S) {
          // 饱和到最大值，其余位置零
          truncatedValue := maxValue.S
        }.elsewhen(inputValue < minValue.S) {
          // 饱和到最小值，其余位置零
          truncatedValue := minValue.S
        }.otherwise {
          // 直接传递，其余位置零
          truncatedValue := inputValue
        }
      }
      io.outputData(i) := truncatedValue
    }.otherwise {
      // en 无效时：仅移位，不进行四舍五入与饱和截位
      val shiftedOnly = Mux(truncateBits > 0.U, (inputValue >> truncateBits).asSInt, inputValue)
      io.outputData(i) := shiftedOnly
    }
  }
}

