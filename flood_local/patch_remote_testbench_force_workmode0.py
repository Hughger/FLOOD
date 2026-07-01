from pathlib import Path


path = Path("src/test/verilog/testbench_r32c32t16.v")
text = path.read_text(encoding="utf-8")
old = "            pwm_w   = planeWorkMode      % (1 << WORK_MODE_WIDTH);\n"
new = "            // Probe mode: force plane work mode to 0 to isolate group16 workMode=3 behavior.\n            pwm_w   = 0;\n"
if old not in text:
    raise SystemExit("planeWorkMode assignment not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
