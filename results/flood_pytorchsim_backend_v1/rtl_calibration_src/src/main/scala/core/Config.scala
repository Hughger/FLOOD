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
// Module     : Config.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: 用于设置FLOOD加速器的整体功能参数
//   0、常规参数(configBusWidth、weightBandWidth、featureMapBandWidth)
//   1、限定其可重构能力的边界(max前缀参数、workMode、tileSize)
//   2、限定其算力资源的大小(rowSize、colSize、tileSize)
//   3、约束其计算精度(dataWidth、outputWidth、finalWidth)
//   4、术语说明：
//     4.1、一轮计算：指FSM从接收到start.valid开始，到outputRouter发送done.valid为止的一段
//       完成计算行为，是MacMachine工作的最小周期
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
 
package FLOOD_Accelerator.core

import chisel3._
import chisel3.util._

object Config {
  // CIMCore参数
  val rowSize = 32
  val colSize = 32

  // 基础参数
  val dataWidth = 8
  val outputWidth = 2*dataWidth+log2Ceil(rowSize)
  val weightBandWidth = colSize * dataWidth // CIMCore的权重总线位宽
  val featureMapBandWidth = weightBandWidth // MacMachine的特征图总线位宽(CIMCore的权重总线的别名)
  
  // MACTree参数
  val pipeline = 2  // 加法树的流水线级数（乘法默认第0级）
  val tLatency = 4 // 一级内计算步骤
  val compressionFactor = 4 // 除乘法流水级与最后一级流水级之外，每个流水级输入结果相邻与前一级的输入结果的压缩比
  require(pipeline >= 2, "pipeline must be >= 2")
  require(tLatency >= 2, "tLatency must be >= 2")
  require(compressionFactor >= 2, "compressionFactor must be >= 2")
  
  // Tile参数
  val maxKernelSize = colSize // Tile内支持的最大卷积2D尺寸k
  val maxWorkMode = 5 // Tile最大的可重构工作模式数量

  // Cluster参数
  val tileSize = 16 // Cluster内Tile的总数
  val finalWidth = outputWidth+log2Ceil(tileSize)+log2Ceil(colSize) // 最终Cluster的输出数据位宽（给outputSram用）
  
  // 配置总线参数
  val configDataWidth = 32
  val configAddrWidth = 32

  // 最优算力效率时的边界参数
  // val maxResolutionH = 2048 // 特征图最大H坐标
  val maxResolutionCol = 768 // 特征图的最大W坐标
  // val maxResolutionC = 4096 // 特征图的最大C坐标 

  // FSM/OutRouter参数
  val maxKernelBlockK = maxKernelSize // 卷积核Block的最大2D尺寸k值
  val maxKernelBlockCout = 32 // 一轮计算中，FLOOD模式下结果图Block的通道数最大为32，NVDLA模式下该参数对应最大像素并行度为512，即512个像素点并行计算
  val maxKernelBlockCin = 1024 // 在（嵌入平面处理处于）输入通道补齐模式的情况下，（多轮情况下，多个卷积核Block等效后）的卷积核Block的最大输入通道数
  val maxGroupSize = tileSize // Cluster中，最大可能实现的组内Tile数
  val maxGroupNum = tileSize // Cluster中，最大可能实现的组内Tile数
  // val maxWorkMode = 5 // 平面工作模式(FSM\OutRouter最大的可重构工作模式数量)
  // NVDLA模式下相关参数
  val maxFeatureBlockWidth = 512 // 最大特征图Block宽度
  val maxPixelParallel = maxKernelBlockCout * tileSize // 最大像素并行参数，也为缓存中存放的特征图Block的宽度，实际使用时像素并行度必然小于该值-k*stride
  require(maxPixelParallel >= maxKernelBlockCout, "maxPixelParallel must be more than maxKernelBlockCout")

  // MacMachine基地址
  val macMachineApbStart = 0x00420000
  val maxMachineApbEnd = 0x00421FFF
  val featureMapSramAxiStart = 0x50000000
  val featureMapSramAxiEnd = 0x500FFFFF

  // MacMachine内部配置参数Id相关参数
  val idWidth = 8
  val tileConfIdStart = 0                 // 第一个tile的配置Id
  val tileConfIdEnd = tileSize-1          // 最后一个tile的配置Id
  val nocConfIdStart = tileSize           // 第一个noc的配置Id
  val nocConfIdEnd = 2*tileSize-2         // 最后一个noc的配置id
  val FSMRouterConfIdStart = 2*tileSize-1 // normal配置Id
  val FSMRouterConfIdEnd = 2*tileSize     // special配置Id 
  val bnConfIdStart = 2*tileSize+1        // BN第一个配置寄存器Id
  val bnConfIdEnd = 2*tileSize+colSize    // BN最后一个配置寄存器Id
  val nvdlaRegId = 2*tileSize+colSize+1   // NVDLA REG配置寄存器Id
  val globalConfId = 2*tileSize+colSize+2 // 全局配置寄存器Id
  val runProcessId = 2*tileSize+colSize+3 // 启动一轮计算
  val interruptFreshId = 2*tileSize+colSize+4   // 请空MacMachine内的中断标示(done/error)
  require(idWidth >= log2Ceil(4*tileSize), s"idWidth($idWidth) 必须大于等于 log2Ceil(4*tileSize)(${log2Ceil(tileSize)})，以保证能唯一标识所有Tile")

  // 临时约束（电路设计不佳导致）
  // require(tLatency>=2, "tLatency must be greater than or equal to 2")
  
  // 参数检查
  require(isPow2(weightBandWidth), "weightBandWidth must be power of 2")
  require(isPow2(rowSize), "rowSize must be power of 2")
  require(isPow2(colSize), "colSize must be power of 2")
  require(rowSize == colSize, "rowSize must be equal to colSize")
  require(maxKernelBlockCout%rowSize == 0, "maxKernelBlockCout must be divisible by rowSize")

  // MACTree参数检查
  require(compressionFactor >= 2, "compressionFactor must be greater than or equal to 2")
  require(rowSize % 2 == 0, "rowSize must be even")
  require(colSize % 2 == 0, "colSize must be even")
  require(math.pow(compressionFactor, pipeline-2) <= rowSize, 
    s"The last stage of MACTreeRefine must have more than 1 input")
  require(compressionFactor % tLatency == 0, 
    s"流水线的输出维度压缩幅度(${compressionFactor})必须是tLatency(${tLatency})的倍数")
  
  // OutRouter/FSM配置寄存器位宽检查
  val kernelBlockKWidth = log2Ceil(maxKernelBlockK)
  val groupSizeWidth = log2Ceil(maxGroupSize)
  val groupNumWidth = log2Ceil(maxGroupNum)
  val cinIdxWidth = log2Ceil(maxKernelBlockCin/rowSize + 1)
  val kernelBlockCoutWidth = log2Ceil(maxKernelBlockCout)
  val resolutionColWidth = log2Ceil(maxResolutionCol/colSize + 1)
  val workModeWidth = log2Ceil(maxWorkMode)
  
  // 辅助函数
  private def isPow2(n: Int): Boolean = (n & (n-1)) == 0 && n > 0

  // 各个SRAM的参数
  // 权重、特征图SRAM的单个数据位宽
  val weightSramDataWidth = 8
  val weightSramAddrWidth = 18
  val featureMapSramDataWidth = 8
  val featureMapSramAddrWidth = 18
  val outputBufferTmpWidth = 16  // 用于中间计算的临时数据位宽
  val outputBufferDataWidth = dataWidth // 包括outputSram与jointSram的位宽，一般为dataWidth来匹配
  // val outputBufferTruncateBits = 0 // 中间结果->输出结果的缩放比例(算数移位的bit位数)
  val outputBufferAddrWidth = 18     // Buffer包括outputSram与jointSram的地址位宽

  require(weightSramDataWidth >= dataWidth, "weightSramDataWidth must not be less than dataWidth")
  require(featureMapSramDataWidth >= dataWidth, "featureMapSramDataWidth must not be less than dataWidth")
  // 各个SRAM的资源开销（B）(衡量乒乓存储资源时，在此基础上*2)
  val weightSramSize = maxKernelBlockCout * (maxKernelBlockCin) * maxKernelBlockK * maxKernelBlockK * ((dataWidth+1)/8) // 卷积核Block的标准尺寸(cout,cin,k,k) = (maxKernelBlockCout,maxKernelBlockCin,maxKernelBlockK,maxKernelBlockK) 故总资源开销为cout*cin*k*k*每个数据的字节数
  val outputSramSize = maxKernelBlockCout * tileSize * (2*colSize) * ((outputBufferDataWidth+1)/8) // 结果图Block的整取部分sram的尺寸(△C,△H,△W) = (maxKernelBlockCout,tileSize,2*colSize) 故总资源开销为通道*△高度*△宽度*每个数据的字节数
  val jointSramSize = maxKernelBlockCout * (3-1) * (maxResolutionCol+colSize) * ((outputBufferDataWidth+1)/8) // 结果图Block的零用部分SRAM的尺寸(△C,3-1,W+1) = (maxKernelBlockCout,3-1,maxFeatureMapW+colSIze) 故总资源开销为通道*k=3时每次运算的高向边界*特征图总宽度*每个数据的字节数; +colSize的目的在与开辟一个拼接数据缓存区，对position>groupNum的数据，count=0则累加缓存区内对应cout上的数据，count=1则覆写缓存区内对应cout上的数据
  // 各个SRAM的地址开销
  val weightSramLength = weightSramSize/(rowSize*((dataWidth+1)/8)) + 1 // 存储器中存储向量，向量维度为rowSize
  val outputSramLength = outputSramSize/(colSize*((outputBufferDataWidth+1)/8)) + 1 // 存储器中存储向量，向量维度为colSize
  val jointSramLength = jointSramSize/(colSize*((outputBufferDataWidth+1)/8)) + 1 // 存储器中存储向量，向量维度为colSize
} 