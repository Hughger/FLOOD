from pathlib import Path


path = Path("src/test/verilog/testbench_r32c32t16.v")
backup = Path("src/test/verilog/testbench_r32c32t16.v.pre_clear_backup")
if not backup.exists():
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

text = path.read_text(encoding="utf-8")
if "task clear_interrupts;" not in text:
    old = """    task cfg_write(input [CFG_ADDRW-1:0] addr, input [CFG_DATAW-1:0] data);
    begin
        @(posedge clk);
        cfg_addr <= addr;
        cfg_data <= data;
        cfg_en   <= 1'b1;
        @(posedge clk);
        cfg_en   <= 1'b0;
    end
    endtask
"""
    new = old + """
    task clear_interrupts;
    integer clear_wait_cycles;
    begin
        cfg_write(INTR_FRESH_ID, 32'h1);
        clear_wait_cycles = 0;
        while ((intr_done === 1'b1 || intr_error === 1'b1) && clear_wait_cycles < 1000) begin
            @(posedge clk);
            clear_wait_cycles = clear_wait_cycles + 1;
        end
        if (intr_done === 1'b1 || intr_error === 1'b1) begin
            $display("[TB][WARN] interrupt clear timeout: done=%0b error=%0b cycles=%0d time=%0t",
                     intr_done, intr_error, clear_wait_cycles, $time);
        end else if (clear_wait_cycles != 0) begin
            $display("[TB] Interrupts cleared after %0d cycles at time %0t", clear_wait_cycles, $time);
        end
    end
    endtask
"""
    if old not in text:
        raise SystemExit("cfg_write block not found")
    text = text.replace(old, new, 1)

if "Ensure stale done/error from previous run is gone" not in text:
    marker = "        // Normal 配置打包（参数化位宽）：[stride | cout-1 | groupNum-1 | groupSize-1 | k-1]\n"
    text = text.replace(
        marker,
        "        // Ensure stale done/error from previous run is gone before reconfiguring.\n"
        "        clear_interrupts();\n\n"
        + marker,
        1,
    )

text = text.replace(
    "        // 清中断\r\n        cfg_write(INTR_FRESH_ID, 32'h1);\r\n",
    "        // 清中断 and wait until the visible interrupt wires deassert.\r\n        clear_interrupts();\r\n",
)
text = text.replace(
    "        // 清中断\n        cfg_write(INTR_FRESH_ID, 32'h1);\n",
    "        // 清中断 and wait until the visible interrupt wires deassert.\n        clear_interrupts();\n",
)

path.write_text(text, encoding="utf-8")
