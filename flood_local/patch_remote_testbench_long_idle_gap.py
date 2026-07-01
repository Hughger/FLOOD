from pathlib import Path


path = Path("src/test/verilog/testbench_r32c32t16.v")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "        for (idle_i = 0; idle_i < 32; idle_i = idle_i + 1) begin\n",
    "        for (idle_i = 0; idle_i < 256; idle_i = idle_i + 1) begin\n",
    1,
)
path.write_text(text, encoding="utf-8")
