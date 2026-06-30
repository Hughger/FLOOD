`timescale 1ns/1ps

module dpSRAM_tb;

    localparam integer ADDR_WIDTH = 4;   // 16 深度，便于演示
    localparam integer DATA_WIDTH = 32;  // 与 dpSRAM.v 默认一致
    localparam integer DEPTH      = (1 << ADDR_WIDTH);

    reg clk;
    reg rst_n;

    // DUT 端口
    reg                  we;
    reg  [ADDR_WIDTH-1:0] waddr;
    reg  [DATA_WIDTH-1:0] wdata;
    reg                  re;
    reg  [ADDR_WIDTH-1:0] raddr;
    wire [DATA_WIDTH-1:0] rdata;

    // 实例化 DUT
    dpSRAM #(
        .ADDR_WIDTH(ADDR_WIDTH),
        .DATA_WIDTH(DATA_WIDTH)
    ) dut (
        .clk   (clk),
        .rst_n (rst_n),
        .we    (we),
        .waddr (waddr),
        .wdata (wdata),
        .re    (re),
        .raddr (raddr),
        .rdata (rdata)
    );

    // 时钟
    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk; // 100MHz
    end

    // 预加载内存
    initial begin
        // 建议使用相对路径运行：工作目录在工程根
        // 允许文件短于 DEPTH，未覆盖的地址保持为X/0
        $readmemh("src/test/verilog/weights_ping.hex", dut.mem);
    end

    // 复位
    initial begin
        rst_n = 1'b0;
        we = 1'b0; waddr = '0; wdata = '0;
        re = 1'b0; raddr = '0;
        #50; // 保持 50ns
        rst_n = 1'b1;
    end

    // 任务：同步读一次（检查1拍延迟）
    task do_read(input [ADDR_WIDTH-1:0] addr);
    begin
        @(posedge clk);
        re    <= 1'b1;
        raddr <= addr;
        @(posedge clk);
        re    <= 1'b0; // 去使能
        // 此时正好是同步读输出拍
        $display("[READ ] t=%0t addr=%0d data=0x%08x", $time, addr, rdata);
    end
    endtask

    // 任务：写然后读回（验证写优先与同步读）
    task do_write_readback(input [ADDR_WIDTH-1:0] addr, input [DATA_WIDTH-1:0] data);
    begin
        @(posedge clk);
        we    <= 1'b1;
        waddr <= addr;
        wdata <= data;
        @(posedge clk);
        we    <= 1'b0;
        // 写后一拍再读
        do_read(addr);
    end
    endtask

    // 产生波形
    initial begin
        $dumpfile("dpSRAM_tb.vcd");
        $dumpvars(0, dpSRAM_tb);
    end

    // 主流程
    integer i;
    initial begin
        @(posedge rst_n);

        // 从预加载内容读取若干地址，观察一拍延迟输出
        for (i = 0; i < 4; i = i + 1) begin
            do_read(i[ADDR_WIDTH-1:0]);
        end

        // 写入新数据并回读
        do_write_readback(4, 32'hA5A5_0001);
        do_write_readback(5, 32'h5A5A_0002);

        // 连续读，验证 re 维持为1 的行为（每拍采样新地址，下一拍输出对应数据）
        @(posedge clk);
        re    <= 1'b1;
        raddr <= 6;
        @(posedge clk);
        raddr <= 7;
        @(posedge clk);
        raddr <= 8;
        @(posedge clk);
        re    <= 1'b0;
        @(posedge clk);

        // 结束
        repeat(5) @(posedge clk);
        $display("dpSRAM_tb finished at t=%0t", $time);
        $finish;
    end

endmodule


