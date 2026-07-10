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
// Module     : OutRouter.scala                                             //
// Author     : 陈挺然                                                      //
// Email      : 18073369150@buaa.edu.cn                                     //
// Description: outputNoc上数据包映射出地址信息并写入到输出缓存中               //
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description            //
//==========================================================================//
// 2025-07-11 |   陈挺然    |   version1  |   初始版本                       //
// yyyy-mm-dd |   author_y  |   version1  |   change_description            //
//////////////////////////////////////////////////////////////////////////////
package FLOOD_Accelerator.machine

import chisel3._
import chisel3.util._
import FLOOD_Accelerator.core.Config
import FLOOD_Accelerator.sram.pingpongBuffer

//////////////////////////////////////////////////////////////////////////////
// Project    : FLOOD_Accelerator                                               //
// Module     : OutRouter.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
//  Description: Router的完整地址映射规则：
// 1. router模块，最主要的功能是根据当前outputNoc中的TileId信息与FSM内的cout,k,groupSize信息，解算outputsram中的写入地址
//   a. 根据groupSize信息，得到特征图Block的行数（TileSize/groupSize）
//   b. 得到结果图的2D尺寸（特征图可以视为一个二维矩阵，其中每个元素为一组，一组对应一个包含colSize个像素的行向量）：
//     i. 行尺寸为TileSize/GroupSize
//     ii. 列尺寸为2
//   c. 结果图的channel必然为1
// 2. 地址计算：
//   a. 以(5,5,rowSize)尺寸的卷积核Block的计算为例，其中k=5，输入通道=rowSize，如图1所示
// 图1

//     i. 前k-1=4批输出Cluter仅会输出TileId=0的数据；
//     ii. 第k批输出Cluster的所有Tile均会向外输出
//       1. 此时Cluster内部的多个Tile（TileSize/groupSize个）会竞争这一个outputNoc，outputNoc内部仲裁器会一一梳理，分多个CLK来依次输出
//       2. Cluster内特征图的一个pingpong更新周期内，要输出若干个输出输出通道对应的结果图，它们的输出方式均如1中描述
//     iii. k值为其它情况时输出方式类似，实际处理时，k值不会超过tileSize
//   b. outputNoc的输出格式
//     i. 数据包包括data、tileId、count、remain四个域
//       1. data为输出数据自身
//       2. tileId为当前占用RRArbiter的tile的唯一本命Id号
//       3. count为当前tile输出的数据的次数
//       4. remain为保留域
//     ii. 每批输出传输两个数据，即count=0一次，count=1一次，每次传输Config.colSize个元素的数据向量
//   c. outputSram的地址计算
//     i. 每个结果图在outputSram中相邻排布
//       1. outputSram内每个存储元素为一个向量，对应colSize个元素，总位宽为 = Conig.finalWidth*colSize
//         a. 如果Config.finalWidth < Config.outputWidth，区outputNoc每个元素的高finalWidth位
//         b. 检查Config.finalWidth 必然小于等于outputWidth
//       2. 故每个Tile的输出数据的完整传输对应两次写入
//     ii. 根据k、groupNum、outputNoc.bits.tileId、outputNoc.bits.count、coutCounter计算地址映射
//       1. coutCounter为cout计数器，从0开始，每次完成第k次握手后+1，当coutCounter==cout且完成第k次握手后coutCounter归零
//       2. 计数与outputNoc的握手总次数hskCounter，每次握手后 + 1
//       3. baseAddr = coutCounter * (groupNum + k - 1) << 1
//       4. 前k-1次握手对应的outputSram写入地址 = baseAddr +hskCounter << 1 + outputNoc.bits.count
//       5. 第k次握手时，Cluster内所有的group的输出Noc均会发出一次outputNoc握手申请，共groupNum个
//         a. 第k次握手对应groupNum*2个数据的传输
//         b. 每个数据对应的outputSram写入地址 = baseAddr +hskCounter<<1 + outputNoc.bits.count + outputNoc.bits.tileId<<1
// Modification History:                             
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2025-07-11 |   陈挺然    |   version1  |   初始版本                 //
// 2025-07-16 |   陈挺然  |   version2  |   通过configBus往OutRouter内写入的k、cout、groupSize、groupNum的四个信息均已经完成-1（如预期k=3，则写入2）              //
//////////////////////////////////////////////////////////////////////////////
class OutRouter(
  val tileId: Int
) extends Module {
  // 从Config对象获取参数
  val colSize = Config.colSize
  val tileSize = Config.tileSize
  val outputWidth = Config.outputWidth
  val finalWidth = Config.finalWidth
  val configDataWidth = Config.configDataWidth
  
  // 配置参数位宽定义
  val kernelBlockKWidth = log2Ceil(Config.maxKernelBlockK)             // 卷积核尺寸 (最大16)
  val kernelBlockCoutWidth = log2Ceil(Config.maxKernelBlockCout)       // 输出通道数（卷积核Block块数）（最大256）
  val groupSizeWidth = log2Ceil(Config.maxGroupSize)              // 每组Tile数量 (最大16)
  val groupNumWidth = log2Ceil(Config.maxGroupNum)              // 组数 (最大16)
  val kernelBlockCinWidth = log2Ceil(Config.maxKernelBlockCin/Config.rowSize)  // 输入通道数（以rowSize个并行度为配置的最小单元）（输入通道最大值4096）
  
  // 计算位宽
  val tileIdWidth = Config.idWidth
  val tileIdUInt = tileId.U(tileIdWidth.W)
  
  // 参数检查
  require(finalWidth <= outputWidth+log2Ceil(tileSize)+log2Ceil(colSize), "finalWidth must be less than or equal to outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)")
  
  // 计算地址位宽
  val addrWidth = log2Ceil(Config.outputSramLength)
  
  // IO定义
  val io = IO(new Bundle {
    // 乒乓控制信号
    val pingpong = Input(Bool())
    
    // 配置总线接口 - 用于获取FSM的配置参数
    val configBus = new Bundle {
      val data = Input(UInt(configDataWidth.W))
      val addr = Input(UInt(Config.configAddrWidth.W))
      val en = Input(Bool())
    }
    
    // 输入NoC接口 - 来自Cluster的输出
    val outputNoc = Flipped(Decoupled(new Bundle {
      val data = Vec(colSize, SInt((outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)).W))
      val featureMapLine = UInt(tileIdWidth.W)
      val count = UInt(8.W)
      val cout = UInt(kernelBlockCoutWidth.W)  // 添加cout信号域
      val kernelRow = UInt(kernelBlockKWidth.W)  // 添加kernelRow信号域
      val remain = UInt(16.W)
    }))
    
    // 输出SRAM接口
    val outputSramWrite = new Bundle {
      val writeEnable = Output(Bool())
      val writeAddress = Output(UInt(addrWidth.W))
      val writeData = Output(UInt((finalWidth * colSize).W))
    }
    
    // done信号 - 当所有输出通道处理完成时发起握手
    val done = Decoupled(Bool())
  })
  
  // 配置寄存器 - 使用pingpongBuffer获取FSM的配置参数
  val configBuffer = Module(new pingpongBuffer(
    size = 1,
    dataWidth = configDataWidth,
    bandWidth = configDataWidth
  ))
  
  // 连接乒乓控制信号
  configBuffer.io.pingpong := io.pingpong
  
  // 连接写使能和地址 - FSM的配置通过FSMId写入
  configBuffer.io.writeEnable := io.configBus.en && (io.configBus.addr === tileIdUInt)
  configBuffer.io.writeAddress := 0.U
  configBuffer.io.writeData := io.configBus.data
  
  // 始终读取配置
  configBuffer.io.readEnable := true.B
  
  // 从配置寄存器中解析参数
  val k = configBuffer.io.readData(kernelBlockKWidth-1, 0) // 卷积核尺寸
  val groupSize = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth - 1, kernelBlockKWidth) // Cluster内每个Tile组内的Tile数量
  val groupNum = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth + groupNumWidth - 1, kernelBlockKWidth + groupSizeWidth) // 组数
  val cin = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCinWidth - 1, kernelBlockKWidth + groupSizeWidth + groupNumWidth) // 输入通道数（以rowSize个并行度为单元）
  val cout = configBuffer.io.readData(kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCinWidth + kernelBlockCoutWidth - 1, kernelBlockKWidth + groupSizeWidth + groupNumWidth + kernelBlockCinWidth) // 输出通道数

  // 地址映射公式
  val baseAddr = (io.outputNoc.bits.cout * (groupNum +& 1.U +& k)) << 1
  val writeAddr = baseAddr + ((k - io.outputNoc.bits.kernelRow) << 1) + 
                 (io.outputNoc.bits.featureMapLine << 1) + io.outputNoc.bits.count
  
  // 简化写入数据截位函数（保持不变）
  def truncateData(dataVec: Vec[SInt], width: Int): UInt = {
    val truncated = Wire(Vec(colSize, UInt(finalWidth.W)))
    for (i <- 0 until colSize) {
      truncated(i) := dataVec(i).asUInt(outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)-1, outputWidth+log2Ceil(tileSize)+log2Ceil(colSize)-finalWidth)
    }
    Cat(truncated.reverse)
  }

  // outputNoc.ready严格握手兼容实现
  val readyReg = RegInit(false.B)
  when(io.outputNoc.valid) {
    readyReg := true.B
  }.otherwise {
    readyReg := false.B
  }
  io.outputNoc.ready := readyReg
  
  // outputSramWrite接口
  io.outputSramWrite.writeEnable := io.outputNoc.fire 
  io.outputSramWrite.writeAddress := writeAddr
  io.outputSramWrite.writeData := truncateData(io.outputNoc.bits.data, finalWidth)

  // done信号逻辑 - 当所有输出通道处理完成时发起握手
  val overFlag = RegInit(false.B)
  val doneFlag = RegInit(false.B)
  val doneValid = RegInit(false.B)
  
  // 当coutCounter归零且完成最后一次握手时，标记overFlag
  when(writeAddr === ( (cout*(groupNum +& 1.U +& k) << 1) + (k << 1) + 
                 (groupNum << 1) + 1.U) ) {
    overFlag := true.B
  }

  // 当overFlag有效，在握手完成时，设置doneFlag
  when(overFlag && !io.outputNoc.fire) {
    doneFlag := true.B
  }
  
  // done握手逻辑
  io.done.valid := doneValid
  io.done.bits := true.B
  
  when(doneFlag && !doneValid) {
    doneValid := true.B
    overFlag := false.B
  }.elsewhen(doneValid && io.done.ready) {
    doneValid := false.B
    doneFlag := false.B
  }
}