from pathlib import Path


path = Path("make_simple_hex.py")
text = path.read_text(encoding="utf-8")

if "def line_multi256" not in text:
    text = text.replace(
        """def line256(seed: int) -> str:
    vals = [((seed + i + 1) & 0xFF) for i in range(32)]
    packed = sum(v << (8 * i) for i, v in enumerate(vals))
    return "{:064x}\\n".format(packed)
""",
        """def line256(seed: int) -> str:
    vals = [((seed + i + 1) & 0xFF) for i in range(32)]
    packed = sum(v << (8 * i) for i, v in enumerate(vals))
    return "{:064x}\\n".format(packed)


def line_multi256(seed: int, chunks: int) -> str:
    words = []
    for chunk in range(chunks):
        vals = [((seed + chunk * 37 + i + 1) & 0xFF) for i in range(32)]
        packed = sum(v << (8 * i) for i, v in enumerate(vals))
        words.append("{:064x}".format(packed))
    return "".join(reversed(words)) + "\\n"
""",
        1,
    )

text = text.replace(
    """    Path("weights_ping.hex").write_text("".join(line256(i) for i in range(weight_lines)), encoding="ascii")
    Path("features.hex").write_text("".join(line256(i * 3) for i in range(feature_lines)), encoding="ascii")
""",
    """    Path("weights_ping.hex").write_text("".join(line256(i) for i in range(weight_lines)), encoding="ascii")
    Path("features.hex").write_text(
        "".join(line_multi256(i * 3, args.res_cols) for i in range(feature_lines)),
        encoding="ascii",
    )
""",
    1,
)

path.write_text(text, encoding="utf-8")
