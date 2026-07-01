from pathlib import Path


path = Path("src/test/verilog/testbench_r32c32t16.v")
text = path.read_text(encoding="utf-8")

if "task wait_idle_gap;" not in text:
    marker = """    task clear_interrupts;
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
    addition = marker + """
    task wait_idle_gap;
    integer idle_i;
    begin
        for (idle_i = 0; idle_i < 32; idle_i = idle_i + 1) begin
            @(posedge clk);
        end
    end
    endtask
"""
    if marker not in text:
        raise SystemExit("clear_interrupts block not found")
    text = text.replace(marker, addition, 1)

old = """        // Ensure stale done/error from previous run is gone before reconfiguring.
        clear_interrupts();

        // Normal 配置打包（参数化位宽）：[stride | cout-1 | groupNum-1 | groupSize-1 | k-1]
"""
new = """        // Ensure stale done/error from previous run is gone before reconfiguring.
        clear_interrupts();
        wait_idle_gap();

        // Normal 配置打包（参数化位宽）：[stride | cout-1 | groupNum-1 | groupSize-1 | k-1]
"""
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
