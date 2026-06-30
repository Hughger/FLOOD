// 简单参数化双端口SRAM：一端口写(we,waddr,wdata)，一端口读(re,raddr,rdata)
// 读为同步读：re在clk上升沿采样，rdata在下一个clk有效
module dpSRAM #(
    parameter ADDR_WIDTH = 8,
    parameter DATA_WIDTH = 32,
    parameter DEPTH = (1 << ADDR_WIDTH)
)(
    input  wire                 clk,
    input  wire                 rst_n,
    // 写端口
    input  wire                 we,
    input  wire [ADDR_WIDTH-1:0] waddr,
    input  wire [DATA_WIDTH-1:0] wdata,
    // 读端口
    input  wire                 re,
    input  wire [ADDR_WIDTH-1:0] raddr,
    output reg  [DATA_WIDTH-1:0] rdata
);

    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];
    reg [ADDR_WIDTH-1:0] raddr_q;
    reg                  re_q;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // do not clear memory for speed; clear control
            raddr_q <= {ADDR_WIDTH{1'b0}};
            re_q    <= 1'b0;
        end else begin
            // 写
            if (we) begin
                mem[waddr] <= wdata;
            end
            // 采样读地址与使能
            raddr_q <= raddr;
            re_q    <= re;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rdata <= {DATA_WIDTH{1'b0}};
        end else begin
            // 同步读：下一拍输出
            if (re_q) begin
                rdata <= mem[raddr_q];
            end
        end
    end

endmodule


