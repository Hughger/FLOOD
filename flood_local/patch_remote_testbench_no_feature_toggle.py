from pathlib import Path


path = Path("src/test/verilog/testbench_r32c32t16.v")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "        featurePingpongFlag = ~featurePingpongFlag;\n",
    "        // Probe mode: keep feature pingpong fixed to avoid switching to stale internal banks.\n"
    "        featurePingpongFlag = featurePingpongFlag;\n",
    1,
)
path.write_text(text, encoding="utf-8")
