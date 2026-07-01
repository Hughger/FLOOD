from pathlib import Path


path = Path("src/test/verilog/testbench_r32c32t16.v")
text = path.read_text(encoding="utf-8")
old = """        // 清中断 and wait until the visible interrupt wires deassert.
        clear_interrupts();
"""
new = """        // Let late output writes / done pulses drain before clearing the visible interrupt.
        wait_idle_gap();
        wait_idle_gap();
        clear_interrupts();
"""
if old not in text:
    raise SystemExit("end clear block not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
