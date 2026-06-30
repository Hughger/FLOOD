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
// Module     : postConfig.scala                                            //
// Author     : 陈挺然                                                      //
// Email      : 18073369150@buaa.edu.cn                                     //
// Description: 汇总MacMachineWrapper及其所有子模块的位宽信息                //
//              • 基于Config.scala中的基础参数计算所有位宽                   //
//              • 提供统一的位宽定义和计算函数                               //
//              • 支持模块间的位宽一致性检查                                 //
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-09-15 |   陈挺然  |   version1  |   初始版本，汇总所有位宽信息      //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////

package FLOOD_Accelerator.core

import chisel3._
import chisel3.util._
import scala.math._

/**
 * 汇总MacMachineWrapper及其所有子模块的位宽信息
 * 基于Config.scala中的基础参数计算所有位宽
 */
object PostConfig {
  
  // ==================== 基础位宽计算 ====================
  
  // 从Config对象获取基础参数
  val rowSize = Config.rowSize
  val colSize = Config.colSize
  val dataWidth = Config.dataWidth
  val outputWidth = Config.outputWidth
  val tileSize = Config.tileSize
  val configDataWidth = Config.configDataWidth
  val configAddrWidth = Config.configAddrWidth
  val weightBandWidth = Config.weightBandWidth
  val featureMapBandWidth = Config.featureMapBandWidth
  val outputBufferTmpWidth = Config.outputBufferTmpWidth
  val outputBufferDataWidth = Config.outputBufferDataWidth
  
  // ==================== MacMachineWrapper 位宽 ====================
  
  // 地址位宽
  val weightAddrWidth = log2Ceil(Config.weightSramLength)
  val outputAddrWidth = log2Ceil(Config.outputSramLength)
  val jointAddrWidth = log2Ceil(Config.jointSramLength)
  
  // 特征图总线位宽
  val featureMapAddrWidth = Config.idWidth + log2Ceil(Config.rowSize)
  
  // ==================== MacMachine 位宽 ====================
  
  // 乒乓控制位宽
  val pingpongWidth = 1
  
  // 特征图总线位宽
  val featureMapTileIdWidth = 2 * log2Ceil(Config.tileSize)
  val featureMapAddrWidthMac = log2Ceil(Config.colSize * Config.rowSize)
  
  // ==================== FSM 位宽 ====================
  
  // 配置参数位宽
  val kernelBlockKWidth = Config.kernelBlockKWidth
  val kernelBlockCoutWidth = Config.kernelBlockCoutWidth
  val groupSizeWidth = Config.groupSizeWidth
  val groupNumWidth = Config.groupNumWidth
  val cinIdxWidth = Config.cinIdxWidth
  val colIdxWidth = Config.resolutionColWidth
  val workModeWidth = Config.workModeWidth
  
  // 输入NoC位宽
  val inputNocDataWidth = dataWidth
  val inputNocWriteIdWidth = Config.idWidth
  val inputNocCountWidth = 8
  val inputNocInputModeWidth = 8
  val inputNocCoutWidth = kernelBlockCoutWidth
  val inputNocKernelRowWidth = kernelBlockKWidth
  val inputNocRemainWidth = 8
  
  // 权重SRAM位宽
  val weightSramDataWidth = Config.weightSramDataWidth
  val weightSramAddrWidth = Config.weightSramAddrWidth
  val weightSramReadDataWidth = rowSize * dataWidth
  
  // 超时计数器位宽
  val timeoutCntWidth = 8
  
  // ==================== Cluster 位宽 ====================
  
  // Tile ID位宽
  val tileIdWidth = Config.idWidth
  
  // 输入NoC位宽（与FSM相同）
  val clusterInputNocDataWidth = dataWidth
  val clusterInputNocWriteIdWidth = tileIdWidth
  val clusterInputNocCountWidth = 8
  val clusterInputNocInputModeWidth = 8
  val clusterInputNocCoutWidth = kernelBlockCoutWidth
  val clusterInputNocKernelRowWidth = kernelBlockKWidth
  val clusterInputNocRemainWidth = 8
  
  // 输出NoC位宽
  val clusterOutputNocDataWidth = outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
  val clusterOutputNocFeatureMapLineWidth = tileIdWidth
  val clusterOutputNocCountWidth = 8
  val clusterOutputNocCoutWidth = kernelBlockCoutWidth
  val clusterOutputNocKernelRowWidth = kernelBlockKWidth
  val clusterOutputNocRemainWidth = 16
  
  // 权重总线位宽
  val weightBusDataWidth = weightBandWidth
  val weightBusTileIdWidth = tileIdWidth
  val weightBusAddrWidth = log2Ceil(colSize * rowSize)
  
  // ==================== Tile 位宽 ====================
  
  // 配置寄存器位宽
  val tileKernelSizeWidth = log2Ceil(Config.maxKernelSize)
  val tileWorkModeWidth = log2Ceil(Config.maxWorkMode)
  val tileRemainWidth = configDataWidth - tileKernelSizeWidth - tileWorkModeWidth - tileIdWidth - tileIdWidth
  
  // 输入NoC位宽（与Cluster输入相同）
  val tileInputNocDataWidth = dataWidth
  val tileInputNocWriteIdWidth = tileIdWidth
  val tileInputNocCountWidth = 8
  val tileInputNocInputModeWidth = 8
  val tileInputNocCoutWidth = kernelBlockCoutWidth
  val tileInputNocKernelRowWidth = kernelBlockKWidth
  val tileInputNocRemainWidth = 8
  
  // 输出NoC位宽（与Cluster输出相同）
  val tileOutputNocDataWidth = outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
  val tileOutputNocFeatureMapLineWidth = tileIdWidth
  val tileOutputNocCountWidth = 8
  val tileOutputNocCoutWidth = kernelBlockCoutWidth
  val tileOutputNocKernelRowWidth = kernelBlockKWidth
  val tileOutputNocRemainWidth = 16
  
  // 互联NoC位宽
  val tileNocDataWidth = outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
  val tileNocRouterWidth = 4
  
  // 移位相加寄存器位宽
  val shiftAddRegWidth = outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
  val shiftAddCounterWidth = 8
  
  // FIFO深度
  val fifoDepth = Config.pipeline + 1
  
  // ==================== InterNoC 位宽 ====================
  
  // 临时数据位宽
  val interNocTmpDataWidth = outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
  
  // 互联NoC数据位宽
  val interNocDataWidth = interNocTmpDataWidth
  val interNocRouterWidth = 4
  
  // ==================== CIMCore 位宽 ====================
  
  // 宏地址位宽
  val cimCoreMacroAddressWidth = log2Ceil(rowSize * colSize * dataWidth / weightBandWidth)
  val cimCoreMacroEnableWidth = log2Ceil(rowSize)
  
  // 向量位宽
  val cimCoreVectorDataWidth = dataWidth
  val cimCoreVectorOutputWidth = outputWidth
  
  // ==================== MACTree 位宽 ====================
  
  // 临时数据位宽（预留累加裕度）
  val macTreeTmpDataWidth = dataWidth * 2 + log2Floor(Config.rowSize).toInt
  
  // 输入输出位宽
  val macTreeInputWidth = dataWidth
  val macTreeOutputWidth = outputWidth
  
  // ==================== OutRouterPlanePost 位宽 ====================
  
  // 配置寄存器位宽
  val outRouterKernelBlockKWidth = kernelBlockKWidth
  val outRouterGroupSizeWidth = groupSizeWidth
  val outRouterGroupNumWidth = groupNumWidth
  val outRouterKernelBlockCoutWidth = kernelBlockCoutWidth
  val outRouterCinIdxWidth = cinIdxWidth
  val outRouterColIdxWidth = colIdxWidth
  val outRouterWorkModeWidth = workModeWidth
  val outRouterTruncateBitsWidth = log2Ceil(outputBufferTmpWidth)
  
  // 输出NoC位宽
  val outRouterOutputNocDataWidth = outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
  val outRouterOutputNocFeatureMapLineWidth = tileIdWidth
  val outRouterOutputNocCountWidth = 8
  val outRouterOutputNocCoutWidth = kernelBlockCoutWidth
  val outRouterOutputNocKernelRowWidth = kernelBlockKWidth
  val outRouterOutputNocRemainWidth = 16
  
  // SRAM位宽
  val outRouterOutputSramDataWidth = colSize * outputBufferTmpWidth
  val outRouterJointSramDataWidth = colSize * outputBufferTmpWidth
  
  // 地址位宽
  val outRouterOutputAddrWidth = outputAddrWidth
  val outRouterJointAddrWidth = jointAddrWidth
  
  // BN参数位宽
  val bnMulParamWidth = 16
  val bnAddParamWidth = 16
  val bnParamWidth = bnMulParamWidth + bnAddParamWidth
  
  // 动作模式位宽
  val actionModeWidth = 8
  
  // ==================== DynamicTruncateData 位宽 ====================
  
  // 默认截位位数位宽
  val defaultTruncateBitsWidth = 8
  
  // 输入输出位宽（根据使用场景动态确定）
  // 注意：outputData的维度与位宽与inputData一致，只有低outputWidth位有效
  def getDynamicTruncateInputWidth(context: String): Int = context match {
    case "s2_toAct" => outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
    case "s2_output" => outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
    case _ => outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)
  }
  
  def getDynamicTruncateOutputWidth(context: String): Int = context match {
    case "s2_toAct" => outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)  // 输出位宽与输入一致
    case "s2_output" => outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)  // 输出位宽与输入一致
    case _ => outputWidth + log2Ceil(tileSize) + log2Ceil(colSize)  // 输出位宽与输入一致
  }
  
  def getDynamicTruncateEffectiveWidth(context: String): Int = context match {
    case "s2_toAct" => outputBufferTmpWidth  // 有效位宽
    case "s2_output" => outputBufferTmpWidth  // 有效位宽
    case _ => outputBufferTmpWidth  // 有效位宽
  }
  
  def getDynamicTruncateVecSize(context: String): Int = context match {
    case "s2_toAct" => colSize
    case "s2_output" => colSize
    case _ => colSize
  }
  
  def getDynamicTruncateBitsWidth(context: String): Int = context match {
    case "s2_toAct" => outRouterTruncateBitsWidth
    case "s2_output" => outRouterTruncateBitsWidth
    case _ => outRouterTruncateBitsWidth
  }
  
  // ==================== 位宽验证函数 ====================
  
  /**
   * 验证位宽一致性
   * @param actualWidth 实际位宽
   * @param expectedWidth 期望位宽
   * @param context 上下文信息
   */
  def validateWidth(actualWidth: Int, expectedWidth: Int, context: String): Unit = {
    require(actualWidth == expectedWidth, 
      s"位宽不一致: $context 实际位宽($actualWidth) != 期望位宽($expectedWidth)")
  }
  
  /**
   * 验证位宽范围
   * @param width 位宽
   * @param minWidth 最小位宽
   * @param maxWidth 最大位宽
   * @param context 上下文信息
   */
  def validateWidthRange(width: Int, minWidth: Int, maxWidth: Int, context: String): Unit = {
    require(width >= minWidth && width <= maxWidth, 
      s"位宽超出范围: $context 位宽($width) 应在 [$minWidth, $maxWidth] 范围内")
  }
  
  // ==================== 位宽计算辅助函数 ====================
  
  /**
   * 计算总线位宽
   * @param elementWidth 元素位宽
   * @param elementCount 元素数量
   * @return 总线位宽
   */
  def calculateBusWidth(elementWidth: Int, elementCount: Int): Int = {
    elementWidth * elementCount
  }
  
  /**
   * 计算地址位宽
   * @param memorySize 存储器大小
   * @return 地址位宽
   */
  def calculateAddrWidth(memorySize: Int): Int = {
    log2Ceil(memorySize)
  }
  
  /**
   * 计算配置寄存器位宽
   * @param fieldWidths 各字段位宽
   * @return 总位宽
   */
  def calculateConfigRegWidth(fieldWidths: Int*): Int = {
    fieldWidths.sum
  }
  
  // ==================== 位宽摘要信息 ====================
  
  /**
   * 获取位宽摘要信息
   * @return 位宽摘要字符串
   */
  def getWidthSummary: String = {
    s"""
    |==================== 位宽摘要信息 ====================
    |基础参数:
    |  rowSize: $rowSize
    |  colSize: $colSize
    |  dataWidth: $dataWidth
    |  outputWidth: $outputWidth
    |  tileSize: $tileSize
    |
    |地址位宽:
    |  weightAddrWidth: $weightAddrWidth
    |  outputAddrWidth: $outputAddrWidth
    |  jointAddrWidth: $jointAddrWidth
    |
    |配置位宽:
    |  configDataWidth: $configDataWidth
    |  configAddrWidth: $configAddrWidth
    |  tileIdWidth: $tileIdWidth
    |
    |NoC位宽:
    |  inputNocDataWidth: $inputNocDataWidth
    |  outputNocDataWidth: $clusterOutputNocDataWidth
    |  interNocDataWidth: $interNocDataWidth
    |
    |SRAM位宽:
    |  weightSramReadDataWidth: $weightSramReadDataWidth
    |  outputSramDataWidth: $outRouterOutputSramDataWidth
    |  jointSramDataWidth: $outRouterJointSramDataWidth
    |
    |截位模块位宽:
    |  truncateBitsWidth: $outRouterTruncateBitsWidth
    |  defaultTruncateBitsWidth: $defaultTruncateBitsWidth
    |====================================================
    """.stripMargin
  }
  
  // ==================== 位宽检查 ====================
  
  /**
   * 执行所有位宽检查
   */
  def performWidthChecks(): Unit = {
    // 检查基础位宽
    validateWidthRange(dataWidth, 1, 32, "dataWidth")
    validateWidthRange(outputWidth, 1, 64, "outputWidth")
    validateWidthRange(tileSize, 1, 32, "tileSize")
    
    // 检查地址位宽
    validateWidthRange(weightAddrWidth, 1, 32, "weightAddrWidth")
    validateWidthRange(outputAddrWidth, 1, 32, "outputAddrWidth")
    validateWidthRange(jointAddrWidth, 1, 32, "jointAddrWidth")
    
    // 检查配置位宽
    validateWidthRange(configDataWidth, 8, 64, "configDataWidth")
    validateWidthRange(configAddrWidth, 8, 64, "configAddrWidth")
    
    // 检查NoC位宽
    validateWidthRange(inputNocDataWidth, 1, 32, "inputNocDataWidth")
    validateWidthRange(clusterOutputNocDataWidth, 1, 64, "clusterOutputNocDataWidth")
    
    // 检查SRAM位宽
    validateWidthRange(weightSramReadDataWidth, 1, 256, "weightSramReadDataWidth")
    validateWidthRange(outRouterOutputSramDataWidth, 1, 256, "outRouterOutputSramDataWidth")
    
    println("所有位宽检查通过！")
  }
}
