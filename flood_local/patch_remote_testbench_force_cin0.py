from pathlib import Path


path = Path("src/test/verilog/testbench_r32c32t16.v")
text = path.read_text(encoding="utf-8")
old = "            cix_w   = cinIdx             % (1 << CIN_IDX_WIDTH);\n"
new = "            // Probe mode: force special cinIdx field to 0 to isolate group16 cinIdx>0 behavior.\n            cix_w   = 0;\n"
if old not in text:
    raise SystemExit("cinIdx assignment not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
