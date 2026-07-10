package FLOOD_Accelerator.machine

import chisel3._
import chisel3.util._
import scala.math._
import FLOOD_Accelerator.core.Config

/**
 * 快速检测数A+1是否是数B的整数倍的模块
 * 
 * 思路：
 * 1. B=0时非法，返回false
 * 2. B=1时，任何数都是1的倍数，返回true，倍数为A+1
 * 3. B=2时，检查A的第0位是否为1（即A+1是否为偶数）
 * 4. B>=3时，计算TileSize内B的所有倍数，与A+1进行比较
 * 
 * 使用Config.tileSize获取tileSize，位宽参考Cluster的tileIdWidth定义
 */
class MultipleDetector extends Module {
  // 从Config对象获取参数
  val tileSize = Config.tileSize
  
  // 计算位宽，参考Cluster内的tileIdWidth定义
  val tileIdWidth = Config.idWidth
  
  val io = IO(new Bundle {
    val A = Input(UInt(tileIdWidth.W))  // 输入数A
    val B = Input(UInt(tileIdWidth.W))  // 输入数B
    val isValid = Output(Bool())      // A+1是否是B的整数倍
    val multiple = Output(UInt(tileIdWidth.W))  // 倍数关系（如果isValid为true）
  })

  // 计算A+1
  val A_plus_1 = io.A + 1.U

  // 处理特殊情况
  when (io.B === 0.U) {
    // B=0时非法
    io.isValid := false.B
    io.multiple := 0.U
  }.elsewhen (io.B === 1.U) {
    // B=1时，任何数都是1的倍数
    io.isValid := true.B
    io.multiple := A_plus_1
  }.elsewhen (io.B === 2.U) {
    // B=2时，检查A+1是否为偶数
    io.isValid := A_plus_1(0) === 0.U
    io.multiple := Mux(A_plus_1(0) === 0.U, A_plus_1 >> 1, 0.U)
  }.otherwise {
    // B>=3时，计算TileSize内B的所有倍数进行比较
    
    // 创建比较器数组，每个比较器检查一个倍数
    val comparators = Seq.tabulate(tileSize) { i =>
      val multiple = (i + 1).U * io.B
      val isMatch = multiple === A_plus_1
      (isMatch, (i + 1).U)
    }
    
    // 使用优先级编码器找到匹配的倍数
    val matchVec = VecInit(comparators.map(_._1))
    val multipleVec = VecInit(comparators.map(_._2))
    
    // 使用优先级编码器
    val encoder = Module(new PriorityEncoder(tileSize))
    encoder.io.in := matchVec
    
    // 检查是否有匹配
    val hasMatch = matchVec.asUInt.orR
    
    io.isValid := hasMatch
    io.multiple := Mux(hasMatch, multipleVec(encoder.io.out), 0.U)
  }
}

/**
 * 优先级编码器模块
 * 输入n位向量，输出最高位1的位置
 */
class PriorityEncoder(n: Int) extends Module {
  val io = IO(new Bundle {
    val in = Input(Vec(n, Bool()))
    val out = Output(UInt(log2Ceil(n).W))
  })
  
  // 使用chisel3.util.PriorityEncoder
  io.out := PriorityEncoder(io.in)
}
