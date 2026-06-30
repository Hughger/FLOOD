#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def f(x):
    return float(x) if x not in ("", None) else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    rows = list(csv.DictReader(open(args.summary, newline="", encoding="utf-8")))
    groups = {}
    for row in rows:
        key = (row["dataset"], row["scenario"])
        groups.setdefault(key, []).append(row)

    out_rows = []
    for (dataset, scenario), items in sorted(groups.items()):
        base = sum(f(r["pytorchsim_cycles"]) for r in items)
        flood = sum(f(r["flood_cycles"]) for r in items)
        ops = ",".join(sorted({r["operator"] for r in items}))
        out_rows.append(
            {
                "dataset": dataset,
                "scenario": scenario,
                "operators": ops,
                "pytorchsim_total_cycles": round(base, 4),
                "flood_total_cycles": round(flood, 4),
                "flood_latency_us": round(flood / 940.0, 6),
                "speedup_vs_pytorchsim": round(base / flood, 6) if flood else "",
            }
        )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    out_md = Path(args.out_md)
    with out_md.open("w", encoding="utf-8") as fh:
        fh.write("# Paper-Level Main Result Table\n\n")
        fh.write("| Dataset | Scenario | Operators | PyTorchSim cycles | FLOOD cycles | FLOOD latency us | Speedup |\n")
        fh.write("|---|---|---|---:|---:|---:|---:|\n")
        for r in out_rows:
            fh.write(
                f"| {r['dataset']} | {r['scenario']} | {r['operators']} | "
                f"{r['pytorchsim_total_cycles']} | {r['flood_total_cycles']} | "
                f"{r['flood_latency_us']} | {r['speedup_vs_pytorchsim']}x |\n"
            )
    print("wrote", out_csv)
    print("wrote", out_md)


if __name__ == "__main__":
    main()
