package FLOOD_Accelerator.machine

import chisel3._
import chisel3.util._
import FLOOD_Accelerator.core.Config

class MacMachineWrapper extends Module {
  val colSize = Config.colSize
  val rowSize = Config.rowSize
  val dataWidth = Config.dataWidth
  val outputBufferDataWidth = Config.outputBufferDataWidth
  val outputBufferTmpWidth = Config.outputBufferTmpWidth
  val weightAddrWidth = log2Ceil(Config.weightSramLength)
  val outputAddrWidth = log2Ceil(Config.outputSramLength)
  val jointAddrWidth = log2Ceil(Config.jointSramLength)

  val io = IO(new Bundle {
    // 配置总线
    val configBus = new Bundle {
      val data = Input(UInt(Config.configDataWidth.W))
      val addr = Input(UInt((Config.configAddrWidth).W))
      val en = Input(Bool())
    }
    // 特征图总线
    val featureMapBus = new Bundle {
      val data = Input(UInt(Config.featureMapBandWidth.W))
      val addr = Input(UInt((Config.idWidth + log2Ceil(Config.rowSize)).W))
      val en = Input(Bool())
    }

    // weightSRAM 两对读写（ping/pong）
    val weightSramReadPing = new Bundle {
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(weightAddrWidth.W))
      val readData = Input(UInt((rowSize * dataWidth).W))
    }
    val weightSramReadPong = new Bundle {
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(weightAddrWidth.W))
      val readData = Input(UInt((rowSize * dataWidth).W))
    }

    // outputSRAM 两对读写（ping/pong）
    val outputSramPing = new Bundle {
      val writeEnable = Output(Bool())
      val writeAddress = Output(UInt(outputAddrWidth.W))
      val writeData = Output(UInt((colSize * Config.outputBufferTmpWidth).W))
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(outputAddrWidth.W))
      val readData = Input(UInt((colSize * Config.outputBufferTmpWidth).W))
    }
    val outputSramPong = new Bundle {
      val writeEnable = Output(Bool())
      val writeAddress = Output(UInt(outputAddrWidth.W))
      val writeData = Output(UInt((colSize * Config.outputBufferTmpWidth).W))
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(outputAddrWidth.W))
      val readData = Input(UInt((colSize * Config.outputBufferTmpWidth).W))
    }

    // 额外的 outputJointSRAM 与 jointSRAM 各一对读写
    val outputJointSram = new Bundle {
      val writeEnable = Output(Bool())
      val writeAddress = Output(UInt(outputAddrWidth.W))
      val writeData = Output(UInt((colSize * Config.outputBufferTmpWidth).W))
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(outputAddrWidth.W))
      val readData = Input(UInt((colSize * Config.outputBufferTmpWidth).W))
    }
    val jointSram = new Bundle {
      val writeEnable = Output(Bool())
      val writeAddress = Output(UInt(jointAddrWidth.W))
      val writeData = Output(UInt((colSize * Config.outputBufferTmpWidth).W))
      val readEnable = Output(Bool())
      val readAddress = Output(UInt(jointAddrWidth.W))
      val readData = Input(UInt((colSize * Config.outputBufferTmpWidth).W))
    }

    // 中断标志信号
    val interrupts = new Bundle {
        val doneInterrupt = Output(Bool()) // done信号中断
        val errorInterrupt = Output(Bool()) // error信号中断
    } 
  })

  val mac = Module(new MacMachine)

  // 直连配置
  mac.io.configBus <> io.configBus
  // 将内部 done 握手在 Wrapper 层直接回握，避免未初始化
  mac.io.FSMdone.ready := mac.io.FSMdone.valid
  mac.io.OutRouterdone.ready := mac.io.OutRouterdone.valid
  // 标准 Decoupled sink：以 fire(ready && valid) 作为握手沿
  val fsmDoneFire = mac.io.FSMdone.valid && mac.io.FSMdone.ready
  val outDoneFire = mac.io.OutRouterdone.valid && mac.io.OutRouterdone.ready

  // 连接特征图总线
  mac.io.featureMapBus.en := io.featureMapBus.en
  mac.io.featureMapBus.tileId := io.featureMapBus.addr(Config.idWidth + log2Ceil(Config.rowSize)-1, log2Ceil(Config.rowSize))
  mac.io.featureMapBus.addr := io.featureMapBus.addr(log2Ceil(Config.rowSize)-1,0)
  mac.io.featureMapBus.data := io.featureMapBus.data

  // 乒乓选择（细分接口）- 声明为 Wire 以便在 VCD 中可见
  val weightSel = Wire(Bool())
  val outputSel = Wire(Bool())
  weightSel := mac.io.weightPingpong // false: ping, true: pong
  outputSel := mac.io.outputPingpong // false: ping, true: pong

  // weightSRAM 读数据反馈（根据乒乓选择）- 添加1个时钟周期的读延迟
  val weightSelReg = RegNext(RegNext(weightSel, false.B), false.B)
  mac.io.weightSramRead.readData := Mux(weightSelReg, io.weightSramReadPong.readData, io.weightSramReadPing.readData)
  // 地址/使能对称驱动
  io.weightSramReadPing.readEnable := mac.io.weightSramRead.readEnable && (!weightSel) // false:ping  true:pong
  io.weightSramReadPing.readAddress := mac.io.weightSramRead.readAddress
  io.weightSramReadPong.readEnable := mac.io.weightSramRead.readEnable && weightSel
  io.weightSramReadPong.readAddress := mac.io.weightSramRead.readAddress

  // 输出区域边界：由 MacMachine 导出（来自 OutRouter）
  // val outputBufferBias = Wire(UInt(outputAddrWidth.W))
  val outputBufferBias = (Config.maxKernelBlockCout * Config.maxGroupNum).U

  // 写地址选通：当地址 >= 边界时，走 outputJointSram；否则走 outputSram ping/pong
  val writeToJoint = Wire(Bool())
  writeToJoint := mac.io.outputSramWrite.writeAddress >= outputBufferBias

  // 输出写：当 biasApply 时，Mux 到 outputJointSram；否则根据乒乓选择到 outputSram ping/pong
  io.outputJointSram.writeEnable := mac.io.outputSramWrite.writeEnable && writeToJoint
  io.outputJointSram.writeAddress := mac.io.outputSramWrite.writeAddress -& outputBufferBias
  io.outputJointSram.writeData := mac.io.outputSramWrite.writeData

  io.outputSramPing.writeEnable := mac.io.outputSramWrite.writeEnable && !writeToJoint && !outputSel
  io.outputSramPing.writeAddress := mac.io.outputSramWrite.writeAddress
  io.outputSramPing.writeData := mac.io.outputSramWrite.writeData

  io.outputSramPong.writeEnable := mac.io.outputSramWrite.writeEnable && !writeToJoint && outputSel
  io.outputSramPong.writeAddress := mac.io.outputSramWrite.writeAddress
  io.outputSramPong.writeData := mac.io.outputSramWrite.writeData

  // 输出读：当 readAddress >= 边界时，Mux 到 outputJointSram；否则根据乒乓选择到 outputSram ping/pong
  val readFromJoint = Wire(Bool())
  readFromJoint := mac.io.outputSramRead.readAddress >= outputBufferBias
  io.outputJointSram.readEnable := mac.io.outputSramRead.readEnable && readFromJoint
  io.outputJointSram.readAddress := mac.io.outputSramRead.readAddress -& outputBufferBias
  
  // 添加1个时钟周期的读延迟 - 地址比较同样延迟对齐
  val readFromJointReg = RegNext(RegNext(readFromJoint, false.B), false.B)
  val outputSelReg = RegNext(RegNext(outputSel, false.B), false.B)
  mac.io.outputSramRead.readData := Mux(readFromJointReg, io.outputJointSram.readData,
                                    Mux(outputSelReg, io.outputSramPong.readData, io.outputSramPing.readData))
  io.outputSramPing.readEnable := mac.io.outputSramRead.readEnable && !readFromJoint && !outputSel
  io.outputSramPing.readAddress := mac.io.outputSramRead.readAddress
  io.outputSramPong.readEnable := mac.io.outputSramRead.readEnable && !readFromJoint && outputSel
  io.outputSramPong.readAddress := mac.io.outputSramRead.readAddress

  // jointSram 直连
  io.jointSram.writeEnable := mac.io.jointSramWrite.writeEnable
  io.jointSram.writeAddress := mac.io.jointSramWrite.writeAddress
  io.jointSram.writeData := mac.io.jointSramWrite.writeData
  io.jointSram.readEnable := mac.io.jointSramRead.readEnable
  io.jointSram.readAddress := mac.io.jointSramRead.readAddress
  mac.io.jointSramRead.readData := io.jointSram.readData

  // ================== 运行控制与中断寄存器 ==================
  // runProcess/interruptFresh 通过 configBus 配置，只要非0即有效
  val runProcessReg = RegInit(0.U(Config.configDataWidth.W))
  val interruptFreshReg = RegInit(0.U(Config.configDataWidth.W))
  val doneInterruptReg = RegInit(false.B)
  val errorInterruptReg = RegInit(false.B)

  // 配置写入
  when(io.configBus.en) {
    when(io.configBus.addr === Config.runProcessId.U) {
      runProcessReg := io.configBus.data
    }.elsewhen(io.configBus.addr === Config.interruptFreshId.U) {
      interruptFreshReg := io.configBus.data
    }
  }

  // runProcess 有效驱动启动，握手后清零
  mac.io.start.valid := runProcessReg(0.U) // 只使用最低位
  mac.io.start.bits := true.B
  when(mac.io.start.ready && mac.io.start.valid) {
    runProcessReg := 0.U
  }

  // 中断设置：error / done 独立寄存
  when(mac.io.error) {
    errorInterruptReg := true.B
  }
  when(outDoneFire) {
    doneInterruptReg := true.B
  }

  io.interrupts.doneInterrupt := doneInterruptReg
  io.interrupts.errorInterrupt := errorInterruptReg

  // 中断刷新：有效即清零，并自清 interruptFreshReg
  when(interruptFreshReg.orR) {
    doneInterruptReg := false.B
    errorInterruptReg := false.B
    interruptFreshReg := 0.U
  }
}


