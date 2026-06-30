import argparse
import csv
import re
from pathlib import Path


PATTERNS = {
    "total_cycles": re.compile(r"Total execution cycles:\s*([0-9]+)"),
    "wall_clock_s": re.compile(r"Wall-clock time for simulation:\s*([0-9.]+)\s*seconds"),
    "dram_aggregate_gbps": re.compile(r"channels 0\.\.[0-9]+ combined \|\s*([0-9.]+)\s*GB/s aggregate"),
}


def parse_log(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    row = {
        "log_file": str(path),
        "total_cycles": "",
        "wall_clock_s": "",
        "dram_aggregate_gbps": "",
        "data_source": "PyTorchSim cycle simulation",
    }
    for key, pattern in PATTERNS.items():
        match = pattern.search(text)
        if match:
            row[key] = match.group(1)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    log_root = Path(args.log_root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    logs = sorted(log_root.rglob("*.log"))
    rows = [parse_log(path) for path in logs]

    fields = ["log_file", "total_cycles", "wall_clock_s", "dram_aggregate_gbps", "data_source"]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
