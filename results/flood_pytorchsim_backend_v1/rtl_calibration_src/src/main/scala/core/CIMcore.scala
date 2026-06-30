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
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
package FLOOD_Accelerator.core

import chisel3._
import chisel3.util._
import scala.math._
import FLOOD_Accelerator.core.Config
import FLOOD_Accelerator.sram.pingpongBuffer

//////////////////////////////////////////////////////////////////////////////
// Project    : FLOOD_Accelerator                                               //
// Module     : CIMcore.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: MAC树，
//1、宏参数为 paral(输入并行度), dataWidth(输入数据位宽), outputWidth(输出数据位宽), 
// pipeline:流水线级数， Tlatency: MACTree的每个流水线级别的耗时
//2、实现paral个输入数据的乘累加计算 
//3、结果量化到outputWidth位宽
//4、根据宏参数，自动构建MACTree的流水线结构
//5、约束为：
//         a. paral必然为pipeline的指数(para = n^pipeline)
//            故每一级流水线的维度压缩比compressionFactor为para^(1/pipeline)
//            故必然可以正常拆分个流水线的计算任务到tLatency个CLK，且每个clk可以计算得到至少一个中间结果
//         b. 每级流水线的结果向量维度为tLatency的倍数（除了最后一级）
//         b. 每级流水线的结果向量维度压缩幅度为tLatency的倍数（除了最后一级）
// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
class MACTree(
  val paral: Int = Config.rowSize,          // 输入并行度
  val dataWidth: Int = Config.dataWidth,      // 输入数据位宽
  val outputWidth: Int = Config.outputWidth,    // 输出数据位宽
  val pipeline: Int = Config.pipeline,       // 流水线级数
  val tLatency: Int = Config.tLatency        // MAC每级流水线的耗时
) extends Module {

  // 生成参数据范围检查
  require(paral >= 1, "paral must be >= 1")
  require(dataWidth >= 1, "dataWidth must be >= 1")
  require(outputWidth >= 1, "outputWidth must be >= 1")
  require(pipeline >= 1, "pipeline must be >= 1")
  require(tLatency >= 1, "tLatency must be >= 1")
  
  // 计算每级流水线的压缩率
  val compressionFactor = Config.compressionFactor
  // require(math.pow(compressionFactor, pipeline) == paral, 
  //   s"paral(${paral})必须是n^pipeline(${compressionFactor}^${pipeline})形式")
  
  // 计算预留了累加裕度的数据位宽
  val tmpDataWidth = dataWidth*2+log2Floor(paral).toInt
  
  val io = IO(new Bundle {
    val inA = Input(Vec(paral, SInt(dataWidth.W)))  // 无握手的输入向量
    val inB = Flipped(Decoupled(Vec(paral, SInt(dataWidth.W))))  // 带握手的输入向量
    val out = Decoupled(SInt(outputWidth.W))  // 带握手的输出
  })
  
  // 计算每个流水级的输出维度
  val stageOutputDims = (0 until pipeline).map(stage => 
    if (stage == 0) paral else if (stage == pipeline-1) 1 else paral / math.pow(compressionFactor, stage).toInt
  )
  
  // 确保每级流水线的结果向量维度为tLatency的倍数（除了最后一级）
  for (i <- 0 until pipeline - 1) { 
    require(stageOutputDims(i) % tLatency == 0, 
      s"Stage ${i+1} input dimension (${stageOutputDims(i)}) must be multiple of tLatency (${tLatency})")
  }

  // 确保每级流水线每clk至少产生一个输出
  for (i <- 1 until pipeline - 1) {
    require(stageOutputDims(i-1) >= tLatency*compressionFactor, // 检查中间流水级的输入维度Dim
      s"Stage ${i+1} output dimension (${stageOutputDims(i)}) must be >= tLatency (${tLatency}) * compressionFactor (${compressionFactor})")
  }

  // 确保每级流水线的结果向量维度压缩幅度为tLatency的倍数（除了最后一级）
  require(compressionFactor % tLatency == 0, 
      s"Pipeline output dimension compression factor (${compressionFactor}) must be multiple of tLatency (${tLatency})")
  
  // 确保流水线的累加计算任务可以被拆分到tLatency个CLK,不同CLK之间的结果不需要跨CLK合并
  require(compressionFactor % tLatency == 0, 
      s"Pipeline accumulation task (${compressionFactor}) must be multiple of tLatency (${tLatency})")

  // 保存各级流水线的状态
  val idle :: computing :: outputting :: Nil = Enum(3)
  val stageStates = RegInit(VecInit(Seq.fill(pipeline)(idle)))
  val stageCounters = RegInit(VecInit(Seq.fill(pipeline)(0.U(log2Ceil(tLatency + 1).W))))
  
  // 第一级流水线的输入缓存
  val inputAReg = RegInit(VecInit(Seq.fill(paral)(0.S(dataWidth.W))))
  val inputBReg = RegInit(VecInit(Seq.fill(paral)(0.S(dataWidth.W))))
  val inputValid = RegInit(false.B)
  
  // 流水线寄存器（存储每级流水线的计算结果）
  // val stageRegisters = stageOutputDims.map(dim => 
  //   RegInit(VecInit(Seq.fill(dim)(0.S(tmpDataWidth.W))))
  // )
  val stageRegistersOut = stageOutputDims.map(dim => 
    RegInit(VecInit(Seq.fill(dim)(0.S(tmpDataWidth.W))))
  )
  // 输出FIFO（深度为4）
  val outputFifo = Module(new Queue(SInt(outputWidth.W), entries = 4))
  // 单级流水累加寄存器（用于时分复用乘法器）
  val accReg = RegInit(0.S((dataWidth*2+log2Floor(paral).toInt).W))
  
  // 初始化FIFO输入信号
  outputFifo.io.enq.bits := 0.S
  outputFifo.io.enq.valid := false.B
  
  // 输入处理逻辑（零等待起算）：一旦 ready&valid，即刻锁存并进入计算
  // when(io.inB.fire) {
  //   inputBReg := io.inB.bits
  //   stageStates(0) := computing
  //   stageCounters(0) := 0.U
  //   accReg := 0.S
  // }
  
 if (pipeline == 1) { // 如果只有一级流水线：计算最终和并量化（时分复用乘法器）
    val processInThisCycle = paral / tLatency // 每拍复用的乘法数量
    // 基于 stageCounters 的 Mux 选择本拍处理的分片
    when(stageStates(0) === computing) {
      when(stageCounters(0) < tLatency.U) {
        val baseIdx = (processInThisCycle.U * stageCounters(0))(log2Ceil(paral)-1,0)
        // 使用寄存的输入，避免握手时序路径
        val subA = Wire(Vec(processInThisCycle, SInt(dataWidth.W)))
        val subB = Wire(Vec(processInThisCycle, SInt(dataWidth.W)))
        for (j <- 0 until processInThisCycle) {
          subA(j) := io.inA(baseIdx + j.U)
          subB(j) := inputBReg(baseIdx + j.U)
        }
        val partialSum = subA.zip(subB).map{ case (a,b) => a * b }.reduce(_ +& _)
        when(stageCounters(0) === 0.U) { accReg := partialSum.asSInt }
          .otherwise { accReg := (accReg + partialSum).asSInt }
        stageCounters(0) := stageCounters(0) + 1.U
      }.otherwise {
        // 量化输出并推入FIFO
        val quantizedOutput = accReg(tmpDataWidth-1, tmpDataWidth-outputWidth).asSInt
        outputFifo.io.enq.bits := quantizedOutput
        outputFifo.io.enq.valid := true.B
        stageStates(0) := outputting
        inputValid := false.B
      }
    }

    // 输出处理
    when(stageStates(0) === outputting) {
      when(outputFifo.io.enq.ready) {
      stageStates(0) := idle
      }
    }
    
  } else {
    // 第一级流水线：执行乘法并初步累加
    switch(stageStates(0)) {
      is(idle) {
        stageCounters(0) := 0.U
        when(io.inB.fire) {
          inputBReg := io.inB.bits
          stageStates(0) := computing
        }
      }
      is(computing) {  
        when(stageCounters(0) < tLatency.U) {
          // 计算需要在当前周期处理的乘累加数量
          val inputDim = paral
          val processInThisCycle = inputDim / tLatency
          // 计算每个输出结果对应的输入的数量
          val inputPerOutput = 1
          // 计算需要在当前周期需要计算的输出结果的数量
          val outputInThisCycle =  processInThisCycle / inputPerOutput
          // 对于当前周期需要处理的每组数据
          for (i <- 0 until outputInThisCycle) {
            val outputIdx = i.U + outputInThisCycle.U * stageCounters(0)
            val inputIdx = inputPerOutput.U * outputIdx
            val subA = VecInit((0 until inputPerOutput).map { j => io.inA(inputIdx + j.U)})
            val subB = VecInit((0 until inputPerOutput).map { j => io.inB.bits(inputIdx + j.U)})
            stageRegistersOut(0)(outputIdx) := subA.zip(subB).map { case (a, b) => a * b }.reduce(_ +& _)
          }
          stageCounters(0) := stageCounters(0) + 1.U
        }
        when(stageCounters(0) >= (tLatency-1).U) {
          // 第一级流水线计算完成
          when (stageStates(1) === idle) {
          // 下一级处于空闲状态
            stageStates(0) := idle
            inputValid := false.B
            stageStates(1) := computing
            stageCounters(1) := 0.U
          }
        }
      }
    }
    
    // 中间流水线级别：执行部分和的累加（参考第一级，计算拍内完成即推进，少一拍）
    for (stage <- 1 until pipeline - 1) {
      switch(stageStates(stage)) {
        is(idle) {
          stageCounters(stage) := 0.U // 初始化计数器
        }
        is(computing) {
          when(stageCounters(stage) < tLatency.U) {
            val inputDim = stageOutputDims(stage - 1)
            val processInThisCycle = inputDim / tLatency
            val inputPerOutput = compressionFactor
            val outputInThisCycle = processInThisCycle / inputPerOutput

            for (i <- 0 until outputInThisCycle) {
              val outputIdx = i.U + outputInThisCycle.U * stageCounters(stage)
              val inputIdx = inputPerOutput.U * outputIdx
              val sub = VecInit((0 until inputPerOutput).map { j => stageRegistersOut(stage-1)(inputIdx + j.U) })
              stageRegistersOut(stage)(outputIdx) := sub.reduce(_ +& _)
            }
            stageCounters(stage) := stageCounters(stage) + 1.U
          }
          // 计数到达最后一拍时，当拍内立即把 token 推给下一级，减少一拍等待
          when(stageCounters(stage) >= (tLatency-1).U) {
            when(stageStates(stage+1) === idle) {
              stageStates(stage) := idle
              stageStates(stage + 1) := computing
              stageCounters(stage + 1) := 0.U
            }
          }
        }
      }
    }
    
    // 最后一级流水线：计算最终和并量化（与中间级相同的“完成即推进”风格，输出作为独立一级）
    val lastStage = pipeline - 1
    switch(stageStates(lastStage)) {
      is(idle) {
        stageCounters(lastStage) := 0.U // 初始化计数器
      }
      is(computing) {
        when(stageCounters(lastStage) < tLatency.U) {
          // 计算需要在当前周期处理的部分和数量（保证整除）
          val inputDim = stageOutputDims(lastStage - 1)
          val processInThisCycle = inputDim / tLatency
          val base = processInThisCycle.U * stageCounters(lastStage)
          val sub = Wire(Vec(processInThisCycle, SInt(tmpDataWidth.W)))
          for (j <- 0 until processInThisCycle) {
            sub(j) := stageRegistersOut(lastStage-1)(base + j.U)
          }
          val tmp_result = sub.reduce(_ +& _)
          when(stageCounters(lastStage) === 0.U) {
            stageRegistersOut(lastStage)(0) := tmp_result
          }.otherwise {
            stageRegistersOut(lastStage)(0) := stageRegistersOut(lastStage)(0) + tmp_result
          }
          when (stageCounters(lastStage) === (tLatency-1).U) {// 到达最后一拍时，将结果推入FIFO，达到最短流水级延时
            val finalResult = (stageRegistersOut(lastStage)(0) + tmp_result)
            val quantizedOutput = finalResult(tmpDataWidth-1, tmpDataWidth-outputWidth).asSInt
            outputFifo.io.enq.bits := quantizedOutput
            outputFifo.io.enq.valid := true.B
          }
          stageCounters(lastStage) := stageCounters(lastStage) + 1.U
        }
        // 到达最后一拍时，同拍内量化并把 token 推到输出级
        when(stageCounters(lastStage) >= (tLatency-1).U) {
          when(outputFifo.io.enq.ready) {
            stageStates(lastStage) := idle
          }
        }
      }
    }
    
  }
  
  // 连接输出FIFO到外部接口
  io.out.bits := outputFifo.io.deq.bits
  io.out.valid := outputFifo.io.deq.valid
  outputFifo.io.deq.ready := io.out.ready
  
  // 设置输入反压
  io.inB.ready := stageStates(0) === idle
}

class MACTreeFlood(
  val paral: Int = Config.rowSize,          // 输入并行度
  val dataWidth: Int = Config.dataWidth,      // 输入数据位宽
  val outputWidth: Int = Config.outputWidth,    // 输出数据位宽
  val pipeline: Int = Config.pipeline,       // 流水线级数
  val tLatency: Int = Config.tLatency        // MAC每级流水线的耗时
) extends Module {

  // 生成参数据范围检查
  require(paral >= 1, "paral must be >= 1")
  require(dataWidth >= 1, "dataWidth must be >= 1")
  require(outputWidth >= 1, "outputWidth must be >= 1")
  require(pipeline >= 1, "pipeline must be >= 1")
  require(tLatency >= 1, "tLatency must be >= 1")
  
  // 计算每级流水线的压缩率
  val compressionFactor = Config.compressionFactor
  // require(math.pow(compressionFactor, pipeline) == paral, 
  //   s"paral(${paral})必须是n^pipeline(${compressionFactor}^${pipeline})形式")
  
  // 计算预留了累加裕度的数据位宽
  val tmpDataWidth = dataWidth*2+log2Floor(paral).toInt
  
  val io = IO(new Bundle {
    val inA = Input(Vec(paral, SInt(dataWidth.W)))  // 无握手的输入向量
    val inB = Flipped(Decoupled(Vec(paral, SInt(dataWidth.W))))  // 带握手的输入向量
    val out = Decoupled(SInt(outputWidth.W))  // 带握手的输出
  })
  
  // 计算每个流水级的输出维度
  val stageOutputDims = (0 until pipeline).map(stage => 
    if (stage == 0) paral else if (stage == pipeline-1) 1 else paral / math.pow(compressionFactor, stage).toInt
  )
  
  // 确保每级流水线的结果向量维度为tLatency的倍数（除了最后一级）
  for (i <- 0 until pipeline - 1) { 
    require(stageOutputDims(i) % tLatency == 0, 
      s"Stage ${i+1} input dimension (${stageOutputDims(i)}) must be multiple of tLatency (${tLatency})")
  }

  // 确保每级流水线每clk至少产生一个输出
  for (i <- 1 until pipeline - 1) {
    require(stageOutputDims(i-1) >= tLatency*compressionFactor, // 检查中间流水级的输入维度Dim
      s"Stage ${i+1} output dimension (${stageOutputDims(i)}) must be >= tLatency (${tLatency}) * compressionFactor (${compressionFactor})")
  }

  // 确保每级流水线的结果向量维度压缩幅度为tLatency的倍数（除了最后一级）
  require(compressionFactor % tLatency == 0, 
      s"Pipeline output dimension compression factor (${compressionFactor}) must be multiple of tLatency (${tLatency})")
  
  // 确保流水线的累加计算任务可以被拆分到tLatency个CLK,不同CLK之间的结果不需要跨CLK合并
  require(compressionFactor % tLatency == 0, 
      s"Pipeline accumulation task (${compressionFactor}) must be multiple of tLatency (${tLatency})")

  // 保存各级流水线的状态
  val idle :: computing :: outputting :: Nil = Enum(3)
  val stageStates = RegInit(VecInit(Seq.fill(pipeline)(idle)))
  val stageCounters = RegInit(VecInit(Seq.fill(pipeline)(0.U(log2Ceil(tLatency + 1).W))))
  
  // 第一级流水线的输入缓存
  val inputValid = RegInit(false.B)
  
  // 流水线寄存器（存储每级流水线的计算结果）
  // val stageRegisters = stageOutputDims.map(dim => 
  //   RegInit(VecInit(Seq.fill(dim)(0.S(tmpDataWidth.W))))
  // )
  val stageRegistersOut = stageOutputDims.map(dim => 
    RegInit(VecInit(Seq.fill(dim)(0.S(tmpDataWidth.W))))
  )
  // 输出FIFO（深度为4）
  val outputFifo = Module(new Queue(SInt(outputWidth.W), entries = 4))
  // 单级流水累加寄存器（用于时分复用乘法器）
  val accReg = RegInit(0.S((dataWidth*2+log2Floor(paral).toInt).W))
  
  // 初始化FIFO输入信号
  outputFifo.io.enq.bits := 0.S
  outputFifo.io.enq.valid := false.B
  
  
  // 第一级流水线：执行乘法并初步累加
  switch(stageStates(0)) {
    is(idle) {
      stageCounters(0) := 0.U
      when(io.inB.fire) {
        stageStates(0) := computing
      }
    }
    is(computing) {  
      when(stageCounters(0) < tLatency.U) {
        // 计算需要在当前周期处理的乘累加数量
        val inputDim = paral
        val processInThisCycle = inputDim / tLatency
        // 计算每个输出结果对应的输入的数量
        val inputPerOutput = 1
        // 计算需要在当前周期需要计算的输出结果的数量
        val outputInThisCycle =  processInThisCycle / inputPerOutput
        // 对于当前周期需要处理的每组数据
        for (i <- 0 until outputInThisCycle) {
          val outputIdx = i.U + outputInThisCycle.U * stageCounters(0)
          val inputIdx = inputPerOutput.U * outputIdx
          val subA = VecInit((0 until inputPerOutput).map { j => io.inA(inputIdx + j.U)})
          val subB = VecInit((0 until inputPerOutput).map { j => io.inB.bits(inputIdx + j.U)})
          stageRegistersOut(0)(outputIdx) := subA.zip(subB).map { case (a, b) => a * b }.reduce(_ +& _)
        }
        stageCounters(0) := stageCounters(0) + 1.U
      }
      when(stageCounters(0) >= (tLatency-1).U) {
        // 第一级流水线计算完成
        when (stageStates(1) === idle) {
        // 下一级处于空闲状态
          stageStates(0) := idle
          inputValid := false.B
          stageStates(1) := computing
          stageCounters(1) := 0.U
        }
        }
      }
    }
    
  // 中间流水线级别：执行部分和的累加（参考第一级，计算拍内完成即推进，少一拍）
    for (stage <- 1 until pipeline - 1) {      
    switch(stageStates(stage)) {
      is(idle) {
        stageCounters(stage) := 0.U // 初始化计数器
      }
      is(computing) {
        when(stageCounters(stage) < tLatency.U) {
          val inputDim = stageOutputDims(stage - 1)
          val processInThisCycle = inputDim / tLatency
          val inputPerOutput = compressionFactor
          val outputInThisCycle = processInThisCycle / inputPerOutput

          for (i <- 0 until outputInThisCycle) {
            val outputIdx = i.U + outputInThisCycle.U * stageCounters(stage)
            val inputIdx = inputPerOutput.U * outputIdx
            val sub = VecInit((0 until inputPerOutput).map { j => stageRegistersOut(stage-1)(inputIdx + j.U) })
            stageRegistersOut(stage)(outputIdx) := sub.reduce(_ +& _)
          }
          stageCounters(stage) := stageCounters(stage) + 1.U
        }
        // 计数到达最后一拍时，当拍内立即把 token 推给下一级，减少一拍等待
        when(stageCounters(stage) >= (tLatency-1).U) {
          when(stageStates(stage+1) === idle) {
            stageStates(stage) := idle
            stageStates(stage + 1) := computing
            stageCounters(stage + 1) := 0.U
          }
          }
        }
      }
    }
    
  // 最后一级流水线：计算最终和并量化（与中间级相同的“完成即推进”风格，输出作为独立一级）
    val lastStage = pipeline - 1
  switch(stageStates(lastStage)) {
    is(idle) {
      stageCounters(lastStage) := 0.U // 初始化计数器
    }
    is(computing) {
      when(stageCounters(lastStage) < tLatency.U) {
        // 计算需要在当前周期处理的部分和数量（保证整除）
        val inputDim = stageOutputDims(lastStage - 1)
        val processInThisCycle = inputDim / tLatency
        val base = processInThisCycle.U * stageCounters(lastStage)
        val sub = Wire(Vec(processInThisCycle, SInt(tmpDataWidth.W)))
        for (j <- 0 until processInThisCycle) {
          sub(j) := stageRegistersOut(lastStage-1)(base + j.U)
        }
        val tmp_result = sub.reduce(_ +& _)
        when(stageCounters(lastStage) === 0.U) {
          stageRegistersOut(lastStage)(0) := tmp_result
        }.otherwise {
          stageRegistersOut(lastStage)(0) := stageRegistersOut(lastStage)(0) + tmp_result
        }
        when (stageCounters(lastStage) === (tLatency-1).U) {// 到达最后一拍时，将结果推入FIFO，达到最短流水级延时
          val finalResult = (stageRegistersOut(lastStage)(0) + tmp_result)
          val quantizedOutput = finalResult(tmpDataWidth-1, tmpDataWidth-outputWidth).asSInt
          outputFifo.io.enq.bits := quantizedOutput
          outputFifo.io.enq.valid := true.B
        }
        stageCounters(lastStage) := stageCounters(lastStage) + 1.U
      }
      // 到达最后一拍时，同拍内量化并把 token 推到输出级
      when(stageCounters(lastStage) >= (tLatency-1).U) {
        when(outputFifo.io.enq.ready) {
          stageStates(lastStage) := idle
        }
      }
    }
  }
    
  
  // 连接输出FIFO到外部接口
  io.out.bits := outputFifo.io.deq.bits
  io.out.valid := outputFifo.io.deq.valid
  outputFifo.io.deq.ready := io.out.ready
  
  // 设置输入反压
  io.inB.ready := stageStates(0) === idle
}

//////////////////////////////////////////////////////////////////////////////
// Project    : FLOOD_Accelerator                                               //
// Module     : MACTreeRefine.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: 针对时序情况进行优化，将地址预计算与加法树流水线化（去除了tLatency机制）
//////////////////////////////////////////////////////////////////////////////  
class MACTreeRefine(
  val paral: Int = Config.rowSize,
  val dataWidth: Int = Config.dataWidth,
  val outputWidth: Int = Config.outputWidth,
  val pipeline: Int = Config.pipeline,
  val tLatency: Int = Config.tLatency
) extends Module {

  // 生成参数据范围检查
  require(paral >= 1, "paral must be >= 1")
  require(dataWidth >= 1, "dataWidth must be >= 1")
  require(outputWidth >= 1, "outputWidth must be >= 1")
  require(pipeline >= 1, "pipeline must be >= 1")
  
  // 每级压缩率：要求 compressionFactor^pipeline == paral
  val compressionFactor = Config.compressionFactor

  // 临时数据位宽
  val tmpDataWidth = dataWidth*2 + log2Floor(paral).toInt

  val io = IO(new Bundle {
    val inA = Input(Vec(paral, SInt(dataWidth.W)))
    val inB = Flipped(Decoupled(Vec(paral, SInt(dataWidth.W))))
    val out = Decoupled(SInt(outputWidth.W))
  })

  // 计算每级输出维度：第0级是乘法（维度=paral），之后每级按 compressionFactor 递减，最后一级强制为1
  val stageDims = (0 to pipeline).map { stage =>
    if (stage == 0) paral else if (stage == pipeline) 1 else paral / math.pow(compressionFactor, stage).toInt
  }

  // 各级寄存器与 valid 标志
  val stageRegs = stageDims.map { dim =>
    RegInit(VecInit(Seq.fill(dim)(0.S(tmpDataWidth.W))))
  }
  val stageValid = RegInit(VecInit(Seq.fill(pipeline + 1)(false.B)))

  // 输入 ready：仅当第0级空闲时可以接收新数据
  io.inB.ready := !stageValid(0)

  // 第0级：输入 fire 时完成乘法并置 valid(0)
  when(io.inB.fire) {
    for (i <- 0 until paral) {
      stageRegs(0)(i) := (io.inA(i) * io.inB.bits(i)).asSInt
    }
    stageValid(0) := true.B
  }

  // 级间推进：每拍把 token 从 s-1 推到 s，并在推进时完成该级加法
  for (s <- 1 to pipeline-1) {
    when(stageValid(s-1) && !stageValid(s)) {
      val inDim = stageDims(s-1)
      val outDim = stageDims(s)
      for (o <- 0 until outDim) {
        val base = o * compressionFactor
        val slice = VecInit((0 until compressionFactor).map { k => stageRegs(s-1)(base + k) })
        stageRegs(s)(o) := slice.reduce(_ +& _)
      }
      stageValid(s) := true.B
      stageValid(s-1) := false.B
    }
  }

  when(stageValid(pipeline-1) && !stageValid(pipeline)) {
    stageRegs(pipeline)(0) := stageRegs(pipeline-1).reduce(_ +& _)
    stageValid(pipeline) := true.B
    stageValid(pipeline-1) := false.B
  }

  // 输出：由最后一级 valid 驱动；量化截位输出
  val lastAcc = stageRegs(pipeline)(0)
  val outBits = lastAcc(tmpDataWidth-1, tmpDataWidth-outputWidth).asSInt
  io.out.bits := outBits
  io.out.valid := stageValid(pipeline)
  when(io.out.fire) {
    stageValid(pipeline) := false.B
  }
}

//////////////////////////////////////////////////////////////////////////////
// Project    : FLOOD_Accelerator                                               //
// Module     : sram.scala                                              //
// Author     : 陈挺然                                                 //
// Email      : 18073369150@buaa.edu.cn                                                //
// Description: CIM core，
//1、主要由Vector、pingpongBuffer与MACTree组成，其中ppB用于乒乓缓存（每行）；MACT用于执行MAC计算（每列）
//2、在使用时，rowSize个ppB（行向量）的第i个元素拆分出来组成一个列向量，提供给第i个MACTree的inA口
//3、colSize个MACT（列向量）共用一个INB接口，INB接口的valid信号为计算的使能信号
//4、宏（macro）参数：
    // a. 阵列尺寸: rowSize, colSize
    // b. 数据精度: dataWidth, outputWidth
    // c. 总线带宽: weightBandWidth
    // d. 流水线信息: pipeline, tLatency 
//5、约束：
    // a.各子模块内部已经添加require，在该模块内无约束
// 6、结果是各个列的MACTree的输出信号out的合并，valid信号&
// 7、其使用方式与MACTree的使用方案相同， 故test.scala具有形似性 
//     a.vectorIn信号有效则启动计算
//     b.vectorIn信号的ready信号表征模块内部的工作状态
//     c.vectorOut信号如果长期不用将阻塞模块的工作
//     d.权重有带宽约束，输入与输出视为无限带宽，其带宽约束在外围近存电路中实现

// Modification History:                                                    //
//    Date    |    Author   |   Version   |   Change Description              //
//============================================================================//
// 2024-12-05 |   陈挺然  |   version1  |   初始版本                 //
// yyyy-mm-dd |   author_y  |   version1  |   change_description              //
//////////////////////////////////////////////////////////////////////////////
class CIMCore(
  val rowSize: Int,
  val colSize: Int, 
  val dataWidth: Int,
  val outputWidth: Int,
  val weightBandWidth: Int,
  val pipeline: Int,
  val tLatency: Int,
) extends Module {
  val macroAddressWidth = log2Ceil(rowSize * colSize * dataWidth / weightBandWidth)
  val macroEnableWidth = log2Ceil(rowSize)

  val io = IO(new Bundle {
    val writeWeightEnable = Input(Bool())
    val writeWeightAddress = Input(UInt(macroAddressWidth.W))
    val writeWeightData = Input(UInt(weightBandWidth.W))
    val vectorIn = Flipped(Decoupled(Vec(rowSize, SInt(outputWidth.W))))
    val vectorOut = Decoupled(Vec(colSize, SInt(outputWidth.W)))
    val pingpong = Input(Bool())
  })
  
  // 1. 例化 rowSize 个 pingpongBuffer 模块 （Buffer存储一个行向量）
  val pingpongBuffers = Seq.fill(colSize)(Module(new pingpongBuffer(size = rowSize, dataWidth = dataWidth, bandWidth = weightBandWidth)))
  for (i <- 0 until rowSize) {
    val buffer = pingpongBuffers(i)
    // 修正权重写入逻辑
    val colSelect = io.writeWeightAddress(macroAddressWidth-1, macroAddressWidth-macroEnableWidth) // 选择具体的Buffer
    val bufferAddressWidth = macroAddressWidth-macroEnableWidth // 地址宽度
    
    // 写使能信号
    buffer.io.writeEnable := io.writeWeightEnable && (colSelect === i.U)
    
    // 地址计算
    if (bufferAddressWidth > 0) {
      buffer.io.writeAddress := io.writeWeightAddress(bufferAddressWidth-1, 0)
    } else {
      buffer.io.writeAddress := 0.U
    }
    
    // 数据写入
    buffer.io.writeData := io.writeWeightData
    buffer.io.readEnable := 1.U // 读取常开
    buffer.io.pingpong := io.pingpong
  }

  // 2. 提取数据成列
  val columns = Wire(Vec(colSize, Vec(rowSize, SInt(dataWidth.W))))
  for (i <- 0 until rowSize) { // 遍历所有行向量
    for (j <- 0 until colSize) { // 遍历行向量内所有元素
      // 从每个 pingpongBuffer 中提取第 j 个元素
      columns(j)(i) := pingpongBuffers(i).io.readData(j * dataWidth + dataWidth - 1, j * dataWidth).asSInt
    }
  }

  // 3. 例化 colSize 个 MAC 模块
  val macs = Seq.fill(colSize)(Module(new MACTreeFlood(paral = rowSize, dataWidth = dataWidth, outputWidth = outputWidth, pipeline = pipeline, tLatency = tLatency)))
  // val macs = Seq.fill(colSize)(Module(new MACTreeRefine(paral = rowSize, dataWidth = dataWidth, outputWidth = outputWidth, pipeline = pipeline, tLatency = tLatency)))
  
  // 4. 寄存vectorIn的数据
  val vectorInReg = RegInit(VecInit(Seq.fill(rowSize)(0.S(dataWidth.W))))
  when(io.vectorIn.fire) {
    vectorInReg := io.vectorIn.bits
  }
  
  // 连接 MAC 模块  
  for (i <- 0 until colSize) {
    macs(i).io.inA := columns(i)
    macs(i).io.inB.valid := io.vectorIn.valid
    macs(i).io.inB.bits := vectorInReg
  }

  // 4. 结果输出握手
  io.vectorOut.bits := VecInit(macs.map(_.io.out.bits))
  io.vectorOut.valid := macs.map(_.io.out.valid).reduce(_ && _)
  macs.foreach(_.io.out.ready := io.vectorOut.ready)
  
  // 设置输入ready信号
  io.vectorIn.ready := macs.map(_.io.inB.ready).reduce(_ && _)
}