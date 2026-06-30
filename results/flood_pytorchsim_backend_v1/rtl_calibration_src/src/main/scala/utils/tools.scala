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
// Module     : tools.scala                                                 //
// Author     : 陈挺然                                                      //
// Email      : 18073369150@buaa.edu.cn                                     //
// Description: 工具类，包含所有模块需要的位宽计算函数
//   主要功能：
//   1. 计算各种配置参数的位宽
//   2. 提供统一的位宽计算接口
//   3. 确保位宽计算的一致性
//   4. 支持Cluster、FSM等模块的位宽需求
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-01-XX |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.utils

import chisel3._
import chisel3.util._
import FLOOD_Accelerator.core.Config

object Tools {
  
  // ============================================================================
  // 基础位宽计算
  // ============================================================================
  
  /**
   * 计算Tile ID位宽
   * @return Tile ID的位宽
   */
  def tileIdWidth: Int = 2 * log2Ceil(Config.tileSize)
  
  /**
   * 计算NoC ID位宽
   * @return NoC ID的位宽
   */
  def nocIdWidth: Int = log2Ceil(Config.tileSize)
  
  /**
   * 计算Tile索引位宽
   * @return Tile索引的位宽
   */
  def tileIndexWidth: Int = log2Ceil(Config.tileSize)
  
  // ============================================================================
  // 配置总线相关位宽
  // ============================================================================
  
  /**
   * 计算卷积核Block K尺寸位宽
   * @return 卷积核Block K尺寸的位宽
   */
  def kernelBlockKWidth: Int = log2Ceil(Config.maxKernelBlockK)
  
  /**
   * 计算卷积核Block输出通道数位宽
   * @return 卷积核Block输出通道数的位宽
   */
  def kernelBlockCoutWidth: Int = log2Ceil(Config.maxKernelBlockCout)
  
  /**
   * 计算卷积核Block输入通道数位宽
   * @return 卷积核Block输入通道数的位宽
   */
  def kernelBlockCinWidth: Int = log2Ceil(Config.maxKernelBlockCin)
  
  /**
   * 计算输入通道索引位宽
   * @return 输入通道索引的位宽
   */
  def cinIdxWidth: Int = log2Ceil(Config.maxKernelBlockCin / Config.rowSize + 1)
  
  /**
   * 计算组大小位宽
   * @return 组大小的位宽
   */
  def groupSizeWidth: Int = log2Ceil(Config.maxGroupSize)
  
  /**
   * 计算组数量位宽
   * @return 组数量的位宽
   */
  def groupNumWidth: Int = log2Ceil(Config.maxGroupNum)
  
  /**
   * 计算分辨率列索引位宽
   * @return 分辨率列索引的位宽
   */
  def resolutionColIdxWidth: Int = log2Ceil(Config.maxResolutionCol / Config.colSize + 1)
  
  /**
   * 计算工作模式位宽
   * @return 工作模式的位宽
   */
  def workModeWidth: Int = log2Ceil(Config.maxWorkMode)
  
  // ============================================================================
  // 数据位宽计算
  // ============================================================================
  
  /**
   * 计算输出数据位宽
   * @return 输出数据的位宽
   */
  def outputWidth: Int = Config.outputWidth
  
  /**
   * 计算最终输出数据位宽
   * @return 最终输出数据的位宽
   */
  def finalWidth: Int = Config.finalWidth
  
  /**
   * 计算权重总线位宽
   * @return 权重总线的位宽
   */
  def weightBandWidth: Int = Config.weightBandWidth
  
  /**
   * 计算特征图总线位宽
   * @return 特征图总线的位宽
   */
  def featureMapBandWidth: Int = Config.featureMapBandWidth
  
  /**
   * 计算配置总线位宽
   * @return 配置总线的位宽
   */
  def configDataWidth: Int = Config.configDataWidth
  
  // ============================================================================
  // SRAM相关位宽计算
  // ============================================================================
  
  /**
   * 计算输出SRAM地址位宽
   * @return 输出SRAM地址的位宽
   */
  def outputSramAddrWidth: Int = log2Ceil(Config.outputSramLength)
  
  /**
   * 计算联合SRAM地址位宽
   * @return 联合SRAM地址的位宽
   */
  def jointSramAddrWidth: Int = log2Ceil(Config.jointSramLength)
  
  /**
   * 计算权重SRAM地址位宽
   * @return 权重SRAM地址的位宽
   */
  def weightSramAddrWidth: Int = log2Ceil(Config.weightSramLength)
  
  /**
   * 计算输出缓冲区数据位宽
   * @return 输出缓冲区数据的位宽
   */
  def outputBufferDataWidth: Int = Config.outputBufferDataWidth
  
  /**
   * 计算权重SRAM数据位宽
   * @return 权重SRAM数据的位宽
   */
  def weightSramDataWidth: Int = Config.weightSramDataWidth
  
  /**
   * 计算特征图SRAM数据位宽
   * @return 特征图SRAM数据的位宽
   */
  def featureMapSramDataWidth: Int = Config.featureMapSramDataWidth
  
  // ============================================================================
  // 流水线相关位宽
  // ============================================================================
  
  /**
   * 计算流水线级数位宽
   * @return 流水线级数的位宽
   */
  def pipelineWidth: Int = log2Ceil(Config.pipeline)
  
  /**
   * 计算延迟位宽
   * @return 延迟的位宽
   */
  def tLatencyWidth: Int = log2Ceil(Config.tLatency)
  
  /**
   * 计算压缩因子位宽
   * @return 压缩因子的位宽
   */
  def compressionFactorWidth: Int = log2Ceil(Config.compressionFactor)
  
  // ============================================================================
  // 计数器和索引位宽
  // ============================================================================
  
  /**
   * 计算计数器位宽
   * @return 计数器的位宽
   */
  def counterWidth: Int = 8
  
  /**
   * 计算剩余数据位宽
   * @return 剩余数据的位宽
   */
  def remainWidth: Int = 16
  
  /**
   * 计算内核行索引位宽
   * @return 内核行索引的位宽
   */
  def kernelRowWidth: Int = kernelBlockKWidth
  
  /**
   * 计算特征图行索引位宽
   * @return 特征图行索引的位宽
   */
  def featureMapLineWidth: Int = tileIdWidth
  
  // ============================================================================
  // 验证函数
  // ============================================================================
  
  /**
   * 验证配置总线位宽是否足够
   * @return 配置总线位宽是否足够
   */
  def isConfigBusWidthSufficient: Boolean = {
    val totalWidth = kernelBlockKWidth + groupSizeWidth + groupNumWidth + 
                     cinIdxWidth + kernelBlockCoutWidth + resolutionColIdxWidth + workModeWidth
    totalWidth <= configDataWidth
  }
  
  /**
   * 获取配置总线总位宽
   * @return 配置总线总位宽
   */
  def getConfigBusTotalWidth: Int = {
    kernelBlockKWidth + groupSizeWidth + groupNumWidth + 
    cinIdxWidth + kernelBlockCoutWidth + resolutionColIdxWidth + workModeWidth
  }
  
  /**
   * 获取配置总线剩余位宽
   * @return 配置总线剩余位宽
   */
  def getConfigBusRemainingWidth: Int = {
    configDataWidth - getConfigBusTotalWidth
  }
  
  // ============================================================================
  // 辅助函数
  // ============================================================================
  
  /**
   * 计算2的幂次方
   * @param n 输入数字
   * @return 是否为2的幂次方
   */
  def isPow2(n: Int): Boolean = (n & (n-1)) == 0 && n > 0
  
  /**
   * 计算向上取整的log2
   * @param n 输入数字
   * @return 向上取整的log2值
   */
  def log2Ceil(n: Int): Int = {
    if (n <= 0) 0
    else if (n == 1) 0
    else {
      val log2 = (math.log(n) / math.log(2)).toInt
      if (math.pow(2, log2) >= n) log2 else log2 + 1
    }
  }
  
  /**
   * 计算向下取整的log2
   * @param n 输入数字
   * @return 向下取整的log2值
   */
  def log2Floor(n: Int): Int = {
    if (n <= 0) 0
    else (math.log(n) / math.log(2)).toInt
  }
} 