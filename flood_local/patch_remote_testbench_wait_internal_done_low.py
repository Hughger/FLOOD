from pathlib import Path


path = Path("src/test/verilog/testbench_r32c32t16.v")
text = path.read_text(encoding="utf-8")

old = """        while ((intr_done === 1'b1 || intr_error === 1'b1) && clear_wait_cycles < 1000) begin
            @(posedge clk);
            clear_wait_cycles = clear_wait_cycles + 1;
        end
        if (intr_done === 1'b1 || intr_error === 1'b1) begin
            $display("[TB][WARN] interrupt clear timeout: done=%0b error=%0b cycles=%0d time=%0t",
                     intr_done, intr_error, clear_wait_cycles, $time);
"""
new = """        while ((intr_done === 1'b1 || intr_error === 1'b1 ||
                dut.mac_io_FSMdone_valid === 1'b1 || dut.mac_io_OutRouterdone_valid === 1'b1) &&
               clear_wait_cycles < 1000) begin
            @(posedge clk);
            clear_wait_cycles = clear_wait_cycles + 1;
        end
        if (intr_done === 1'b1 || intr_error === 1'b1 ||
            dut.mac_io_FSMdone_valid === 1'b1 || dut.mac_io_OutRouterdone_valid === 1'b1) begin
            $display("[TB][WARN] interrupt clear timeout: done=%0b error=%0b fsm_done=%0b out_done=%0b cycles=%0d time=%0t",
                     intr_done, intr_error, dut.mac_io_FSMdone_valid, dut.mac_io_OutRouterdone_valid, clear_wait_cycles, $time);
"""
if old not in text:
    raise SystemExit("clear wait block not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
