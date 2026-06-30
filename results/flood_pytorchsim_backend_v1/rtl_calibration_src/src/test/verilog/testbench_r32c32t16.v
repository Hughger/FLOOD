`timescale 1ns/10ps

module testbench;

    // 根据 generated/MacMachineWrapper.v 端口位宽调整参数
    localparam integer CFG_DATAW               = 32;
    localparam integer CFG_ADDRW               = 32;
    localparam integer FEAT_DATAW              = 256;  // io_featureMapBus_data
    localparam integer FEAT_ADDRW              = 13;   // io_featureMapBus_addr
    localparam integer WEIGHT_ADDR_WIDTH       = 21;   // io_weightSramRead*_readAddress
    localparam integer WEIGHT_DATAW            = 256;  // io_weightSramRead*_readData
    localparam integer OUTPUT_ADDR_WIDTH       = 11;   // io_outputSram*_read/writeAddress
    localparam integer OUTBUF_DATAW            = 512;  // io_outputSram*_read/writeData
    localparam integer JOINT_ADDR_WIDTH        = 11;   // io_jointSram_read/writeAddress
    localparam integer ID_WIDTH                = 8;    // derived from addr[12:5] in Wrapper
    localparam integer ROW_ADDR_WIDTH          = 5;    // lower bits of addr[4:0]
    localparam integer CIN_IDX_WIDTH           = 6;    // log2ceil(1024/32+1)=log2ceil(33)=6
    localparam integer RES_COL_IDX_WIDTH       = 5;    // log2ceil(768/32+1)=log2ceil(25)=5
    localparam integer WORK_MODE_WIDTH         = 3;    // log2ceil(maxWorkMode) = log2ceil(5)
    localparam integer TRUNC_BITS_WIDTH        = 4;    // log2ceil(outputBufferTmpWidth) = log2ceil(16)
    localparam integer COUT_WIDTH              = 5;    // log2ceil(maxKernelBlockCout) = log2ceil(512)
    localparam integer GROUP_SIZE_WIDTH        = 4;    // log2ceil(maxGroupSize) = log2ceil(tileSize=16)=4
    localparam integer GROUP_NUM_WIDTH         = 4;    // log2ceil(maxGroupNum)  = log2ceil(tileSize=16)=4
    localparam integer K_WIDTH                 = 5;    // log2ceil(maxKernelBlockK) = log2ceil(colSize=32)=5
    localparam integer STRIDE_WIDTH            = K_WIDTH; // 与k保持一致的位宽
    // 依据 Scala 默认（rowSize=4, colSize=4, tileSize=4）推断（支持 -D 覆盖）
`ifndef ROW_SIZE
    localparam integer ROW_SIZE                = 32;
`else
    localparam integer ROW_SIZE                = `ROW_SIZE;
`endif
`ifndef COL_SIZE
    localparam integer COL_SIZE                = 32;
`else
    localparam integer COL_SIZE                = `COL_SIZE;
`endif
`ifndef TILE_SIZE
    localparam integer TILE_SIZE               = 16;
`else
    localparam integer TILE_SIZE               = `TILE_SIZE;
`endif
    // 顶层宏参数映射（均可用 -D 覆盖）
`ifndef K_PARAM
    localparam integer K_PARAM                 = 3;
`else
    localparam integer K_PARAM                 = `K_PARAM;
`endif
`ifndef COUT_PARAM
    localparam integer COUT_PARAM              = 2;
`else
    localparam integer COUT_PARAM              = `COUT_PARAM;
`endif
`ifndef GROUP_SIZE_PARAM
    localparam integer GROUP_SIZE_PARAM        = 4;
`else
    localparam integer GROUP_SIZE_PARAM        = `GROUP_SIZE_PARAM;
`endif
`ifndef GROUP_NUM_PARAM
    localparam integer GROUP_NUM_PARAM        = 4;
`else
    localparam integer GROUP_NUM_PARAM        = `GROUP_NUM_PARAM;
`endif
`ifndef STRIDE_PARAM
    localparam integer STRIDE_PARAM            = 1; 
`else
    localparam integer STRIDE_PARAM            = `STRIDE_PARAM;
`endif
    // 允许通过编译参数覆盖：+define+RES_COL_TOTAL=N / +define+RES_ROW_TOTAL=N
`ifndef CIN_IDX_TOTAL
    localparam integer CIN_IDX_TOTAL             = 2;
`else
    localparam integer CIN_IDX_TOTAL             = `CIN_IDX_TOTAL;
`endif
`ifndef RES_COL_TOTAL
    localparam integer RES_COL_TOTAL = 2;
`else
    localparam integer RES_COL_TOTAL = `RES_COL_TOTAL;
`endif
`ifndef RES_ROW_TOTAL
    localparam integer RES_ROW_TOTAL = 2;
`else
    localparam integer RES_ROW_TOTAL = `RES_ROW_TOTAL;
`endif

    reg clk;
    reg rst_n;

    // DUT 端口声明（与 MacMachineWrapper.scala 对齐）
    // configBus
    reg  [CFG_DATAW-1:0] cfg_data;
    reg  [CFG_ADDRW-1:0] cfg_addr;
    reg         cfg_en;

    // featureMapBus
    reg  [FEAT_DATAW-1:0] feature_data;  // 对应 io_featureMapBus_data
    reg  [FEAT_ADDRW-1:0] feature_addr;  // 对应 io_featureMapBus_addr
    reg         feature_en;

    // weight ping
    wire                        wping_re;
    wire [WEIGHT_ADDR_WIDTH-1:0] wping_raddr;
    wire [WEIGHT_DATAW-1:0]     wping_rdata;
    // weight pong
    wire                        wpong_re;
    wire [WEIGHT_ADDR_WIDTH-1:0] wpong_raddr;
    wire [WEIGHT_DATAW-1:0]     wpong_rdata;

    // output ping
    wire                        oping_we;
    wire [OUTPUT_ADDR_WIDTH-1:0] oping_waddr;
    wire [OUTBUF_DATAW-1:0]     oping_wdata;
    wire                        oping_re;
    wire [OUTPUT_ADDR_WIDTH-1:0] oping_raddr;
    wire [OUTBUF_DATAW-1:0]     oping_rdata;

    // output pong
    wire                        opong_we;
    wire [OUTPUT_ADDR_WIDTH-1:0] opong_waddr;
    wire [OUTBUF_DATAW-1:0]     opong_wdata;
    wire                        opong_re;
    wire [OUTPUT_ADDR_WIDTH-1:0] opong_raddr;
    wire [OUTBUF_DATAW-1:0]     opong_rdata;

    // outputJoint
    wire                        ojoint_we;
    wire [OUTPUT_ADDR_WIDTH-1:0] ojoint_waddr;
    wire [OUTBUF_DATAW-1:0]     ojoint_wdata;
    wire                        ojoint_re;
    wire [OUTPUT_ADDR_WIDTH-1:0] ojoint_raddr;
    wire [OUTBUF_DATAW-1:0]     ojoint_rdata;

    // joint
    wire                        joint_we;
    wire [JOINT_ADDR_WIDTH-1:0] joint_waddr;
    wire [OUTBUF_DATAW-1:0]     joint_wdata;
    wire                        joint_re;
    wire [JOINT_ADDR_WIDTH-1:0] joint_raddr;
    wire [OUTBUF_DATAW-1:0]     joint_rdata;

    // interrupts
    wire intr_done;
    wire intr_error;

    // DUT 实例（名称需吻合生成的 Verilog 模块名）
    // 若后端导出名不是 MacMachineWrapper，请据实际名修改
    MacMachineWrapper dut (
        .clock (clk),
        .reset (~rst_n),
        // configBus
        .io_configBus_data   (cfg_data),
        .io_configBus_addr   (cfg_addr),
        .io_configBus_en     (cfg_en),
        // featureMapBus
        .io_featureMapBus_data (feature_data),
        .io_featureMapBus_addr (feature_addr),
        .io_featureMapBus_en   (feature_en),
        // weight read ping
        .io_weightSramReadPing_readEnable (wping_re),
        .io_weightSramReadPing_readAddress(wping_raddr),
        .io_weightSramReadPing_readData   (wping_rdata),
        // weight read pong
        .io_weightSramReadPong_readEnable (wpong_re),
        .io_weightSramReadPong_readAddress(wpong_raddr),
        .io_weightSramReadPong_readData   (wpong_rdata),
        // output ping
        .io_outputSramPing_writeEnable (oping_we),
        .io_outputSramPing_writeAddress(oping_waddr),
        .io_outputSramPing_writeData   (oping_wdata),
        .io_outputSramPing_readEnable  (oping_re),
        .io_outputSramPing_readAddress (oping_raddr),
        .io_outputSramPing_readData    (oping_rdata),
        // output pong
        .io_outputSramPong_writeEnable (opong_we),
        .io_outputSramPong_writeAddress(opong_waddr),
        .io_outputSramPong_writeData   (opong_wdata),
        .io_outputSramPong_readEnable  (opong_re),
        .io_outputSramPong_readAddress (opong_raddr),
        .io_outputSramPong_readData    (opong_rdata),
        // outputJoint
        .io_outputJointSram_writeEnable (ojoint_we),
        .io_outputJointSram_writeAddress(ojoint_waddr),
        .io_outputJointSram_writeData   (ojoint_wdata),
        .io_outputJointSram_readEnable  (ojoint_re),
        .io_outputJointSram_readAddress (ojoint_raddr),
        .io_outputJointSram_readData    (ojoint_rdata),
        // joint
        .io_jointSram_writeEnable (joint_we),
        .io_jointSram_writeAddress(joint_waddr),
        .io_jointSram_writeData   (joint_wdata),
        .io_jointSram_readEnable  (joint_re),
        .io_jointSram_readAddress (joint_raddr),
        .io_jointSram_readData    (joint_rdata),
        // interrupts
        .io_interrupts_doneInterrupt (intr_done),
        .io_interrupts_errorInterrupt(intr_error)
    );

    // 顶层循环控制变量提前声明，避免在 initial 语句后再声明引发语法错误
    integer resolutionRowIdx, resolutionColIdx, cinIdx;

    // ========== 用 dpSRAM 替换所有存储 ==========
    // weight ping - 使用与Wrapper匹配的数据位宽
    dpSRAM #(
        .ADDR_WIDTH(WEIGHT_ADDR_WIDTH),
        .DATA_WIDTH(WEIGHT_DATAW)
    ) u_wping (
        .clk   (clk),
        .rst_n (rst_n),
        .we    (1'b0),
        .waddr ({WEIGHT_ADDR_WIDTH{1'b0}}),
        .wdata ({WEIGHT_DATAW{1'b0}}),
        .re    (wping_re),
        .raddr (wping_raddr),
        .rdata (wping_rdata)
    );

    // weight pong - 使用与Wrapper匹配的数据位宽
    dpSRAM #(
        .ADDR_WIDTH(WEIGHT_ADDR_WIDTH),
        .DATA_WIDTH(WEIGHT_DATAW)
    ) u_wpong (
        .clk   (clk),
        .rst_n (rst_n),
        .we    (1'b0),
        .waddr ({WEIGHT_ADDR_WIDTH{1'b0}}),
        .wdata ({WEIGHT_DATAW{1'b0}}),
        .re    (wpong_re),
        .raddr (wpong_raddr),
        .rdata (wpong_rdata)
    );

    // output ping
    dpSRAM #(
        .ADDR_WIDTH(OUTPUT_ADDR_WIDTH),
        .DATA_WIDTH(OUTBUF_DATAW)
    ) u_oping (
        .clk   (clk),
        .rst_n (rst_n),
        .we    (oping_we),
        .waddr (oping_waddr),
        .wdata (oping_wdata),
        .re    (oping_re),
        .raddr (oping_raddr),
        .rdata (oping_rdata)
    );

    // output pong
    dpSRAM #(
        .ADDR_WIDTH(OUTPUT_ADDR_WIDTH),
        .DATA_WIDTH(OUTBUF_DATAW)
    ) u_opong (
        .clk   (clk),
        .rst_n (rst_n),
        .we    (opong_we),
        .waddr (opong_waddr),
        .wdata (opong_wdata),
        .re    (opong_re),
        .raddr (opong_raddr),
        .rdata (opong_rdata)
    );

    // outputJoint
    dpSRAM #(
        .ADDR_WIDTH(OUTPUT_ADDR_WIDTH),
        .DATA_WIDTH(OUTBUF_DATAW)
    ) u_ojoint (
        .clk   (clk),
        .rst_n (rst_n),
        .we    (ojoint_we),
        .waddr (ojoint_waddr),
        .wdata (ojoint_wdata),
        .re    (ojoint_re),
        .raddr (ojoint_raddr),
        .rdata (ojoint_rdata)
    );

    // joint
    dpSRAM #(
        .ADDR_WIDTH(JOINT_ADDR_WIDTH),
        .DATA_WIDTH(OUTBUF_DATAW)
    ) u_joint (
        .clk   (clk),
        .rst_n (rst_n),
        .we    (joint_we),
        .waddr (joint_waddr),
        .wdata (joint_wdata),
        .re    (joint_re),
        .raddr (joint_raddr),
        .rdata (joint_rdata)
    );

    // ========== 时钟复位 ==========
    initial begin
        clk = 1'b0;
        forever #1 clk = ~clk; // 100MHz
    end

    initial begin
        rst_n = 1'b0;
        cfg_data = 0; cfg_addr = 0; cfg_en = 0;
        feature_data = 0; feature_addr = 0; feature_en = 0;
        repeat(10) @(posedge clk);
        @(negedge clk);
        rst_n = 1'b1;
    end

    // 生成波形便于调试
    initial begin
`ifdef DUMP_VCD
        $dumpfile("testbench_r32c32t16.vcd");
        $dumpvars(0, testbench);
`endif
    end

    // ========== 全局超时看门狗 ==========
    // 在每次配置写入脉冲（cfg_en 上升沿）或 done 中断上升沿时清零；
    // 若计数超过 4*cout*k*k*groupSize*10 则报错并结束仿真。
    integer watchdog_counter;
    integer watchdog_limit;
    reg prev_cfg_en;
    reg prev_intr_done;

    // 动态计算阈值，随着 k/cout/groupSize 的变化而更新
    always @* begin
        watchdog_limit = 20000
                       + (RES_COL_TOTAL * RES_ROW_TOTAL * CIN_IDX_TOTAL * ROW_SIZE * GROUP_SIZE_PARAM * TILE_SIZE * 8)
                       + (cout * k * k * groupSize * 2000);
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            watchdog_counter <= 0;
            prev_cfg_en      <= 1'b0;
            prev_intr_done   <= 1'b0;
        end else begin
            // 上升沿检测
            if ((cfg_en & ~prev_cfg_en) || (intr_done & ~prev_intr_done)) begin
                watchdog_counter <= 0;
            end else begin
                watchdog_counter <= watchdog_counter + 1;
            end

            // 触发超时
            if (watchdog_counter >= watchdog_limit) begin
                $display("[ERROR][WDOG] Global timeout reached: counter=%0d limit=%0d", watchdog_counter, watchdog_limit);
                $finish;
            end

            // 记录前一拍
            prev_cfg_en    <= cfg_en;
            prev_intr_done <= intr_done;
        end
    end

    // ========== 常量与ID ==========
    // 根据 Config.scala 计算配置ID：
    // tileConfIdStart = 0, tileConfIdEnd = tileSize-1 = 3
    // nocConfIdStart = tileSize = 4, nocConfIdEnd = 2*tileSize-2 = 6
    // FSMRouterConfIdStart = 2*tileSize-1 = 7, FSMRouterConfIdEnd = 2*tileSize = 8
    // globalConfId = 2*tileSize+colSize+2 = 14
    // runProcessId = 3*tileSize = 12, interruptFreshId = 3*tileSize+1 = 13
    localparam [CFG_ADDRW-1:0] TILE_CONF_START    = 32'd0;   // 0x00..0x0F (Tile 0..15)
    localparam [CFG_ADDRW-1:0] NOC_CONF_START     = 32'd16;  // 0x10.. (InterNoC)
    localparam [CFG_ADDRW-1:0] FSM_CONF_START_ID  = 32'd31;  // 0x1F normal
    localparam [CFG_ADDRW-1:0] FSM_CONF_END_ID    = 32'd32;  // 0x20 special
    localparam [CFG_ADDRW-1:0] GLOBAL_CONF_ID     = 32'd66;  // 0x42 global
    localparam [CFG_ADDRW-1:0] RUN_PROCESS_ID     = 32'd67;  // 0x43 run
    localparam [CFG_ADDRW-1:0] INTR_FRESH_ID      = 32'd68;  // 0x44 interruptFresh

    task cfg_write(input [CFG_ADDRW-1:0] addr, input [CFG_DATAW-1:0] data);
    begin
        @(posedge clk);
        cfg_addr <= addr;
        cfg_data <= data;
        cfg_en   <= 1'b1;
        @(posedge clk);
        cfg_en   <= 1'b0;
    end
    endtask

    // ========== 预置权重SRAM、准备特征数据 ==========
    // 使用层次化路径将权重写入 dpSRAM 内部存储
    // 文件位于 src/test/verilog/：weights_ping.hex, weights_init.hex（若无可按需复制）
    initial begin
        @(posedge rst_n);
        // 预置权重
        $display("[TB] $readmemh -> u_wping.mem from weights_ping.hex");
        $readmemh("weights_ping.hex", u_wping.mem);
        // $display("[TB] $readmemh -> u_wpong.mem from weights_pong.hex");  // 暂时只使用ping
        // $readmemh("weights_pong.hex", u_wpong.mem);
    end

    // 全局特征图内存（整体，不按tile拆分），每行包含 resolutionColIdxTotal*FEAT_DATAW 比特

    reg [RES_COL_TOTAL*FEAT_DATAW-1:0] feat_mem_global [0:(1<<FEAT_ADDRW)-1];
    integer f_feat, lines_feat, c;
    reg [1023:0] buf_feat;
    integer height_calc, width_calc, cin_calc, feature_lines_expect;
    initial begin
        @(posedge rst_n);
        $display("[TB] $readmemh -> feat_mem_global from features.hex");
        $readmemh("features.hex", feat_mem_global);
        // 统计文件行数并与期望规模对比
        height_calc = (TILE_SIZE / groupSize) * resolutionRowIdxTotal; // groupNum*resRows
        width_calc  = COL_SIZE * resolutionColIdxTotal;
        cin_calc    = cinIdxTotal * ROW_SIZE * groupSize;
        feature_lines_expect = height_calc * cin_calc;
        f_feat = $fopen("features.hex", "r");
        if (f_feat) begin
            lines_feat = 0;
            while (!$feof(f_feat)) begin
                c = $fgets(buf_feat, f_feat);
                if (c != 0) lines_feat = lines_feat + 1;
            end
            $fclose(f_feat);
            $display("[CHK] features.hex lines=%0d expect=%0d (height=%0d width=%0d cin=%0d)",
                     lines_feat, feature_lines_expect, height_calc, width_calc, cin_calc);
            if (lines_feat != feature_lines_expect)
                $display("[WARN] features size mismatch: got %0d lines, expect %0d", lines_feat, feature_lines_expect);
        end else begin
            $display("[WARN] cannot open features.hex for size check");
        end
    end

    // ========== 参数对齐 Scala WrapperTest ==========

    integer k, cout, groupSize, groupNum, stride;
    integer cinIdxTotal, resolutionColIdxTotal, resolutionRowIdxTotal;
    integer planeWorkMode;
    integer dataFlowMode, truncateBits, truncateEn;
    // 乒乓控制（参考 WrapperTest）
    reg featurePingpongFlag;
    reg weightPingpongFlag;
    reg outputPingpongFlag;
    reg pingpongEnFlag;  // 为1时，权重/输出在每次run后翻转；为0时保持不变
    initial begin
        // 默认值来自宏参数（可被 plusargs 覆盖）
        k = K_PARAM; cout = COUT_PARAM; groupSize = GROUP_SIZE_PARAM; groupNum = GROUP_NUM_PARAM; stride = STRIDE_PARAM;
        cinIdxTotal = CIN_IDX_TOTAL; resolutionColIdxTotal = RES_COL_TOTAL; resolutionRowIdxTotal = RES_ROW_TOTAL;
        // 乒乓初值：与 Scala 测试保持一致
        featurePingpongFlag = 1'b0;
        weightPingpongFlag  = 1'b0;
        outputPingpongFlag  = 1'b0;
        pingpongEnFlag      = 1'b0;  // 默认关闭，可按需改为1
        // 允许通过 plusargs 覆盖
        if ($value$plusargs("K=%d", k)) $display("[ARGS] K=%0d", k);
        if ($value$plusargs("COUT=%d", cout)) $display("[ARGS] COUT=%0d", cout);
        if ($value$plusargs("GROUP_SIZE=%d", groupSize)) begin
            groupNum = TILE_SIZE / groupSize;
            $display("[ARGS] GROUP_SIZE=%0d -> groupNum=%0d", groupSize, groupNum);
        end
        if ($value$plusargs("CIN_IDX_TOTAL=%d", cinIdxTotal)) $display("[ARGS] CIN_IDX_TOTAL=%0d", cinIdxTotal);
        if ($value$plusargs("RES_COLS=%d", resolutionColIdxTotal)) $display("[ARGS] RES_COLS=%0d", resolutionColIdxTotal);
        if ($value$plusargs("RES_ROWS=%d", resolutionRowIdxTotal)) $display("[ARGS] RES_ROWS=%0d", resolutionRowIdxTotal);
        planeWorkMode = 0; dataFlowMode = 0; truncateBits = 0; truncateEn = 0;
        $display("[TB] Params: k=%0d cout=%0d groupSize=%0d groupNum=%0d stride=%0d rowSize=%0d colSize=%0d tileSize=%0d",
                 k, cout, groupSize, groupNum, stride, ROW_SIZE, COL_SIZE, TILE_SIZE);
    end

    // ========== Tile/NoC 配置（与 Scala 一致的关系） ==========
    task config_tiles_and_noc;
    integer tileId;
    integer featureMapLine, writeId;
    integer nocId, upperGroup, lowerGroup, systolic, add, deliver;
    reg [CFG_DATAW-1:0] configData;
    // 对齐 Wrapper/Tile 配置位宽：featureMapLine/writeId 使用 idWidth(=8)，
    // workMode 使用 log2Ceil(maxWorkMode)=3，比特；k 使用 kernelBlockKWidth=5 比特
    reg [7:0] featureMapLine2;
    reg [2:0] workMode2;
    reg [7:0] writeId2;
    reg [4:0] kminus1_2;
    begin
        // Tile 配置（与 Scala 中 writeId/featureMapLine 映射一致）
        for (tileId = 0; tileId < TILE_SIZE; tileId = tileId + 1) begin
            featureMapLine = tileId / groupSize;
            writeId = (groupSize-1) - (tileId % groupSize);
            // 打包: [remain | featureMapLine | workMode | writeId | kernelSize]
            // 这里按简单位宽：tileIdWidth=2, kernelSizeWidth=2, workModeWidth=3
            featureMapLine2 = featureMapLine;
            workMode2 = 0;
            writeId2 = writeId;
            kminus1_2 = (k-1);
            configData = { {(CFG_DATAW-21){1'b0}}, featureMapLine2, workMode2, writeId2, kminus1_2 };
            cfg_write(TILE_CONF_START + tileId, configData);
            $display("[TB] Tile%0d config: featureMapLine=%0d writeId=%0d kernelSize=%0d data=0x%08x",
                     tileId, featureMapLine, writeId, k-1, configData);
        end
        // NoC 路由配置
        for (nocId = 0; nocId < TILE_SIZE-1; nocId = nocId + 1) begin
            upperGroup = nocId / groupSize;
            lowerGroup = (nocId + 1) / groupSize;
            systolic = (upperGroup != lowerGroup);
            add = (upperGroup == lowerGroup);
            deliver = 1;
            configData = { {(CFG_DATAW-4){1'b0}}, (deliver?1'b1:1'b0), (systolic?1'b1:1'b0), (add?1'b1:1'b0), 1'b0 };
            cfg_write(NOC_CONF_START + nocId, configData);
            $display("[TB] NoC%0d config: deliver=%0d systolic=%0d add=%0d data=0x%08x",
                     nocId, deliver, systolic, add, configData);
        end
    end
    endtask

    // ========== 从全局features.hex驱动 featureMapBus ==========
    // features.hex 打包方式：每行4个8bit元素（32bit），width=colSize*resolutionColIdxTotal=8 ⇒ 每个地址行对应2条32bit数据。
    task drive_feature_from_files(input integer cinIdx, input integer resolutionColIdx, input integer resolutionRowIdx);
    integer tileId, r;
    integer startRowCin, startRowHeight, startRow;
    integer addr_in_hex;
    begin
        for (tileId = 0; tileId < TILE_SIZE; tileId = tileId + 1) begin
            // 修正：添加缺失的乘法因子 (groupNum * resolutionRowIdxTotal)
            startRowCin = (cinIdx * (ROW_SIZE*groupSize) + ((groupSize-1 - (tileId % groupSize)) * ROW_SIZE)) * (groupNum * resolutionRowIdxTotal);
            startRowHeight = (resolutionRowIdx * groupNum) + (tileId / groupSize);
            startRow = startRowCin + startRowHeight;
            for (r = 0; r < ROW_SIZE; r = r + 1) begin
                // 修正：保持与 Scala 一致的 addr_in_hex 计算
                addr_in_hex = startRow + r*groupNum*resolutionRowIdxTotal;
                @(posedge clk);
                feature_addr <= {tileId[ID_WIDTH-1:0], r[ROW_ADDR_WIDTH-1:0]};
                feature_data <= feat_mem_global[addr_in_hex][resolutionColIdx*FEAT_DATAW +: FEAT_DATAW];
                feature_en   <= 1'b1;
                // $display("[FEAT] tile=%0d row=%0d addr_in_hex=%0d colIdx=%0d data=0x%08x",
                //          tileId, r, addr_in_hex, resolutionColIdx,
                //          feat_mem_global[addr_in_hex][resolutionColIdx*FEAT_DATAW +: FEAT_DATAW]);
                @(posedge clk);
                feature_en   <= 1'b0;
            end
        end
    end
endtask

    // ========== 一次 runProcess ==========
    task run_process(input integer cinIdx, input integer resolutionColIdx, input integer resolutionRowIdx);
    integer isFinalCinIdx, bnEn, actEn, poolEn, actionMode;
    integer run_wait_cycles;
    reg [CFG_DATAW-1:0] normalConfig, specialConfig, globalConf;
    reg [STRIDE_WIDTH-1:0]      stride_w;
    reg [COUT_WIDTH-1:0]        cout_m1_w;
    reg [GROUP_NUM_WIDTH-1:0]   groupNum_m1_w;
    reg [GROUP_SIZE_WIDTH-1:0]  groupSize_m1_w;
    reg [K_WIDTH-1:0]           k_m1_w;
    reg [TRUNC_BITS_WIDTH-1:0]     trunc_w;
    reg [WORK_MODE_WIDTH-1:0]      pwm_w;
    reg [RES_COL_IDX_WIDTH-1:0]    rci_w;
    reg [CIN_IDX_WIDTH-1:0]        cix_w;
    reg [4:0] action5;
    begin
        isFinalCinIdx = (cinIdx == (cinIdxTotal - 1));
        bnEn = 0; actEn = 0; poolEn = 0; // 与 Scala 中 actionEn=false 对齐
        actionMode = (dataFlowMode << 0) | (isFinalCinIdx << 1) | (bnEn << 2) | (actEn << 3) | (poolEn << 4);
        $display("[TB] cinIdx=%0d resolutionColIdx=%0d resolutionRowIdx=%0d: dataFlowMode=%0d isFinalCinIdx=%0d bnEn=%0d actEn=%0d poolEn=%0d => 0x%08x",
                 cinIdx, resolutionColIdx, resolutionRowIdx, dataFlowMode, isFinalCinIdx, bnEn, actEn, poolEn, actionMode);
        // Normal 配置打包（参数化位宽）：[stride | cout-1 | groupNum-1 | groupSize-1 | k-1]
        begin
            // k=1时stride生效，否则为0
            stride_w      = (stride-1) % (1 << STRIDE_WIDTH);
            cout_m1_w      = (cout-1)       % (1 << COUT_WIDTH);
            groupNum_m1_w  = (groupNum-1)   % (1 << GROUP_NUM_WIDTH);
            groupSize_m1_w = (groupSize-1)  % (1 << GROUP_SIZE_WIDTH);
            k_m1_w         = (k-1)          % (1 << K_WIDTH);
            normalConfig = { {(CFG_DATAW-(STRIDE_WIDTH+COUT_WIDTH+GROUP_NUM_WIDTH+GROUP_SIZE_WIDTH+K_WIDTH)){1'b0}},
                             stride_w, cout_m1_w, groupNum_m1_w, groupSize_m1_w, k_m1_w };
        end
        $display("[TB] Normal config: k=%0d groupSize=%0d groupNum=%0d cout=%0d stride=%0d => 0x%08x",
                 k, groupSize, groupNum, cout, stride, normalConfig);
        cfg_write(FSM_CONF_START_ID, normalConfig);

        // Special 配置打包（参数化位宽）：[truncateEn | truncateBits | planeWorkMode | resolutionColIdx | cinIdx]
        begin
            trunc_w = truncateBits       % (1 << TRUNC_BITS_WIDTH);
            pwm_w   = planeWorkMode      % (1 << WORK_MODE_WIDTH);
            rci_w   = resolutionColIdx   % (1 << RES_COL_IDX_WIDTH);
            cix_w   = cinIdx             % (1 << CIN_IDX_WIDTH);
            specialConfig = { (truncateEn ? 1'b1 : 1'b0), trunc_w, pwm_w, rci_w, cix_w };
        end
        $display("[TB] Special config: cinIdx=%0d resolutionColIdx=%0d workMode=%0d truncateEn=%0d truncateBits=%0d => 0x%08x",
                 cinIdx, resolutionColIdx, planeWorkMode, truncateEn, truncateBits, specialConfig);
        cfg_write(FSM_CONF_END_ID, specialConfig);

        // 驱动特征图
        drive_feature_from_files(cinIdx, resolutionColIdx, resolutionRowIdx);

        // 更新乒乓标志：feature 每次翻转；weight/output 受 pingpongEnFlag 控制
        featurePingpongFlag = ~featurePingpongFlag;
        if (pingpongEnFlag) weightPingpongFlag = ~weightPingpongFlag;
        if (pingpongEnFlag) outputPingpongFlag = ~outputPingpongFlag;

        // 乒乓标志编码到全局配置高位：{feature, weight, output}
        begin
            action5 = actionMode % 32;
            // 3个标志 + 保留位 + action5（低位）；标志已是1bit标量，直接拼接
            globalConf = { featurePingpongFlag, weightPingpongFlag, outputPingpongFlag, {(CFG_DATAW-3-5){1'b0}}, action5 };
        end
        $display("[TB] Global config: featurePingpong=%0d weightPingpong=%0d outputPingpong=%0d actionMode=0x%0x => 0x%08x",
                 featurePingpongFlag, weightPingpongFlag, outputPingpongFlag, actionMode, globalConf);
        cfg_write(GLOBAL_CONF_ID, globalConf);

        // 触发 run
        $display("[TB] Trigger run at time %0t", $time);
        cfg_write(RUN_PROCESS_ID, 32'h1);
        $display("[TB] Run command accepted at time %0t", $time);

        // 等待 done 或 error
        run_wait_cycles = 0;
        while (intr_done !== 1'b1 && intr_error !== 1'b1 && run_wait_cycles < 2000000) begin
            @(posedge clk);
            run_wait_cycles = run_wait_cycles + 1;
            if ((run_wait_cycles % 10000) == 0) begin
                $display("[TB][RUN_WAIT] cycles=%0d time=%0t done=%0b error=%0b", run_wait_cycles, $time, intr_done, intr_error);
                $display("[TB][DBG] runReg=%h start_v=%0b start_r=%0b fsm_done=%0b out_done=%0b out_fire=%0b mac_err=%0b doneReg=%0b errReg=%0b",
                         dut.runProcessReg,
                         dut.mac_io_start_valid,
                         dut.mac_io_start_ready,
                         dut.mac_io_FSMdone_valid,
                         dut.mac_io_OutRouterdone_valid,
                         dut.outDoneFire,
                         dut.mac_io_error,
                         dut.doneInterruptReg,
                         dut.errorInterruptReg);
                $display("[TB][FSM] state=%0d inGrp=%0d kCol=%0d kRow=%0d cout=%0d pix=%0d inValid=%0b inReady=%0b wEn=%0b wAddr=%0d",
                         dut.mac.fsm.state,
                         dut.mac.fsm.inputGroupCnt,
                         dut.mac.fsm.kernelColCnt,
                         dut.mac.fsm.kernelRowCnt,
                         dut.mac.fsm.outputChannelCnt,
                         dut.mac.fsm.pixelPosCnt,
                         dut.mac.fsm.io_inputNoc_valid,
                         dut.mac.fsm.io_inputNoc_ready,
                         dut.mac.fsm.io_weightSramRead_readEnable,
                         dut.mac.fsm.io_weightSramRead_readAddress);
            end
        end
        if (intr_done) $display("[TB] Done interrupt after %0d cycles at time %0t", run_wait_cycles, $time);
        if (intr_error) $display("[TB] Error interrupt after %0d cycles at time %0t", run_wait_cycles, $time);
        if (!intr_done && !intr_error) begin
            $display("[TB][FATAL] run wait timeout after %0d cycles at time %0t", run_wait_cycles, $time);
            $finish;
        end
        // 清中断
        cfg_write(INTR_FRESH_ID, 32'h1);
    end
    endtask

    // ========== 打印输出结果任务（类似DataConverter.printOutputSramResults） ==========
    task print_output_results;
        input integer resolutionColIdx;
        input integer resolutionRowIdx;
        integer file_handle;
        integer c, row, addr, col;
        integer start_addr;
        integer rows_per_channel;
        integer addresses_per_channel;
        reg [OUTBUF_DATAW-1:0] temp_data;
        reg signed [15:0] signed_data;
        begin
            
             // 构建输出文件名（带行列后缀）
             file_handle = $fopen($sformatf("actual_output_results_r%d_c%d.csv", resolutionRowIdx, resolutionColIdx), "w");
             
             if (file_handle == 0) begin
                 $display("[ERROR] Cannot open file");
                 $finish;
             end
             
             // 每个输出通道的数据行数（只打印前groupNum行）
             rows_per_channel = groupNum;
             // 每个输出通道的地址数（每地址一整行）
             addresses_per_channel = rows_per_channel;
             
             $display("[TB] Starting to print output results: resolutionColIdx=%0d resolutionRowIdx=%0d", resolutionColIdx, resolutionRowIdx);
             $display("[TB] Parameters: cout=%0d groupNum=%0d colSize=%0d", cout, groupNum, COL_SIZE);
            
            for (c = 0; c < cout; c = c + 1) begin  // 遍历输出通道
                start_addr = c * addresses_per_channel;
                
                // 直接写出每个地址的一行（期望每行长度为 1*colSize）
                for (row = 0; row < rows_per_channel; row = row + 1) begin
                    addr = start_addr + row;
                    
                    // 根据当前乒乓状态选择对应的SRAM
                    if (!outputPingpongFlag) begin
                        // 使用乒outputSram
                        for (col = 0; col < COL_SIZE; col = col + 1) begin
                            if (col > 0) $fwrite(file_handle, ",");
                            // 通过SRAM读接口读取数据
                            force oping_raddr = addr;
                            force oping_re = 1'b1;
                            @(posedge clk);
                            @(posedge clk);
                            force oping_re = 1'b0;
                            temp_data = oping_rdata[col*16 +: 16];
                            signed_data = temp_data[15:0];
                            
                            // Debug prints for data conversion
                            $display("DEBUG: oping_rdata=0x%h, col=%d, addr=%d, temp_data=%d, signed_data=%d", 
                                     oping_rdata, col, addr, temp_data, signed_data);
                            
                            $fwrite(file_handle, "%d", signed_data);
                            release oping_raddr;
                            release oping_re;
                        end
                    end else begin
                        // 使用乓outputSram
                        for (col = 0; col < COL_SIZE; col = col + 1) begin
                            if (col > 0) $fwrite(file_handle, ",");
                            // 通过SRAM读接口读取数据
                            force opong_raddr = addr;
                            force opong_re = 1'b1;
                            @(posedge clk);
                            force opong_re = 1'b0;
                            temp_data = opong_rdata[col*16 +: 16];
                            signed_data = temp_data[15:0];
                            $fwrite(file_handle, "%d", signed_data);
                            release opong_raddr;
                            release opong_re;
                        end
                    end
                    $fwrite(file_handle, "\n");
                end
                
                // 通道间用空行分隔（最后一个通道后不加空行）
                if (c < cout - 1) begin
                    $fwrite(file_handle, "\n");
                end
            end
            
             $fclose(file_handle);
             $display("[TB] Output results written to file");
        end
    endtask

    // ========== 打印Joint SRAM结果任务（类似DataConverter.printJointSramData） ==========
    task print_joint_results;
        integer file_handle;
        integer c, row, addr, col;
        integer start_addr;
        integer joint_rows_per_channel;
        integer joint_addresses_per_channel;
        reg [OUTBUF_DATAW-1:0] temp_data;
        reg signed [15:0] signed_data;
        begin
            
             // 构建输出文件名
             file_handle = $fopen("actual_joint_results.csv", "w");
             
             if (file_handle == 0) begin
                 $display("[ERROR] Cannot open file");
                 $finish;
             end
             
             // jointSram的结果图行数为k-1
             joint_rows_per_channel = k - 1;
             // 每地址即为一整行
             joint_addresses_per_channel = joint_rows_per_channel;
             
             $display("[TB] Starting to print Joint SRAM results");
             $display("[TB] Parameters: cout=%0d k=%0d colSize=%0d", cout, k, COL_SIZE);
            
            for (c = 0; c < cout; c = c + 1) begin  // 遍历输出通道
                start_addr = c * joint_addresses_per_channel;
                
                // 直接将每个地址的一整行写入CSV
                for (row = 0; row < joint_rows_per_channel; row = row + 1) begin
                    addr = start_addr + row;
                    
                    for (col = 0; col < COL_SIZE; col = col + 1) begin
                        if (col > 0) $fwrite(file_handle, ",");
                        // 通过SRAM读接口读取数据
                        force joint_raddr = addr;
                        force joint_re = 1'b1;
                        @(posedge clk);
                        force joint_re = 1'b0;
                        temp_data = joint_rdata[col*16 +: 16];
                        signed_data = temp_data[15:0];
                        $fwrite(file_handle, "%d", signed_data);
                        release joint_raddr;
                        release joint_re;
                    end
                    $fwrite(file_handle, "\n");
                end
                
                // 通道间用空行分隔（最后一个通道后不加空行）
                if (c < cout - 1) begin
                    $fwrite(file_handle, "\n");
                end
            end
            
             $fclose(file_handle);
             $display("[TB] Joint SRAM results written to file");
        end
    endtask

    // ========== 顶层测试流程（对齐 Scala 三层循环） ==========
    initial begin : main_loop
        @(posedge rst_n);
        config_tiles_and_noc();

        // rowIdx -> colIdx -> cinIdx
        for (resolutionRowIdx = 0; resolutionRowIdx < resolutionRowIdxTotal; resolutionRowIdx = resolutionRowIdx + 1) begin
            for (resolutionColIdx = 0; resolutionColIdx < resolutionColIdxTotal; resolutionColIdx = resolutionColIdx + 1) begin
                // 计算 planeWorkMode
                if (resolutionRowIdx == 0) begin
                    if (resolutionColIdx == 0) planeWorkMode = 0; else planeWorkMode = 4;
                end else begin
                    if (resolutionColIdx == 0) planeWorkMode = 1; else planeWorkMode = 2;
                end
                run_process(0, resolutionColIdx, resolutionRowIdx);
                planeWorkMode = 3;
                for (cinIdx = 1; cinIdx < cinIdxTotal; cinIdx = cinIdx + 1) begin
                    run_process(cinIdx, resolutionColIdx, resolutionRowIdx);
                end
                
                // 每轮CinIdx遍历完成后，打印输出结果
                print_output_results(resolutionColIdx, resolutionRowIdx);
                
                if (intr_error) begin
                    $display("[TB][FATAL] errorInterrupt asserted");
                    disable main_loop;
                end
            end
        end
        
        // 所有计算完成后，打印Joint SRAM结果
        print_joint_results;
        
        repeat(50) @(posedge clk);
        $finish;
    end

    // ========== 运行期信号打印（便于调试） ==========
    // 记录中断沿
    reg intr_done_q, intr_error_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            intr_done_q  <= 1'b0;
            intr_error_q <= 1'b0;
        end else begin
            if (intr_done & ~intr_done_q) begin
                $display("[INTR] done=1 at time %0t", $time);
            end
            if (intr_error & ~intr_error_q) begin
                $display("[INTR] error=1 at time %0t", $time);
                $finish;
            end
            intr_done_q  <= intr_done;
            intr_error_q <= intr_error;
        end
    end

    // 权重读请求打印（地址/端口）
    always @(posedge clk) begin
        if (wping_re) $display("[WREAD] ping  addr=%0d data=0x%08x", wping_raddr, wping_rdata);
        if (wpong_re) $display("[WREAD] pong  addr=%0d data=0x%08x", wpong_raddr, wpong_rdata);
    end

    // 输出/联合SRAM写入打印
    always @(posedge clk) begin
        if (oping_we)  $display("[OWR]   ping  addr=%0d data=0x%08x", oping_waddr, oping_wdata);
        if (opong_we)  $display("[OWR]   pong  addr=%0d data=0x%08x", opong_waddr, opong_wdata);
        if (ojoint_we) $display("[OWR]   jointO addr=%0d data=0x%08x", ojoint_waddr, ojoint_wdata);
        if (joint_we)  $display("[OWR]   joint  addr=%0d data=0x%08x", joint_waddr, joint_wdata);
    end

endmodule


