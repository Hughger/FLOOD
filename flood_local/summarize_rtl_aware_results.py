#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def read_csv(path: Path, dataset: str):
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row = dict(row)
            row["dataset"] = dataset
            rows.append(row)
    return rows


def as_float(row, key):
    try:
        value = row.get(key, "")
        return float(value) if value not in ("", None) else 0.0
    except ValueError:
        return 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--inputs", nargs="+", required=True, help="dataset_name=csv_path")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for item in args.inputs:
        dataset, path = item.split("=", 1)
        rows.extend(read_csv(Path(path), dataset))

    combined = out_dir / "combined_rtl_aware_results.csv"
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with combined.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    groups = {}
    for row in rows:
        key = (row.get("dataset", ""), row.get("operator", ""))
        groups.setdefault(key, []).append(row)

    summary_rows = []
    for (dataset, operator), items in sorted(groups.items()):
        baseline = sum(as_float(r, "total_cycles") for r in items)
        rtl = sum(as_float(r, "rtl_total_cycles") for r in items)
        if rtl <= 0:
            continue
        useful = sum(as_float(r, "rtl_useful_macs") for r in items)
        padded = sum(as_float(r, "rtl_padded_macs") for r in items)
        summary_rows.append(
            {
                "dataset": dataset,
                "operator": operator,
                "num_rows": len(items),
                "baseline_total_cycles": int(baseline),
                "rtl_total_cycles": int(rtl),
                "rtl_latency_us": rtl / 940.0 if rtl else "",
                "speedup_vs_pytorchsim": baseline / rtl if rtl else "",
                "weighted_compute_utilization": useful / padded if padded else "",
            }
        )

    summary = out_dir / "operator_summary.csv"
    with summary.open("w", newline="", encoding="utf-8") as f:
        fields = list(summary_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    ranked = sorted(rows, key=lambda r: as_float(r, "rtl_total_cycles"), reverse=True)
    top = out_dir / "top_rtl_bottlenecks.csv"
    top_fields = [
        "dataset",
        "id",
        "operator",
        "shape_args",
        "total_cycles",
        "rtl_total_cycles",
        "rtl_latency_us",
        "rtl_speedup_vs_pytorchsim_baseline",
        "rtl_compute_utilization",
        "rtl_compute_cycles",
        "rtl_activation_load_cycles",
        "rtl_weight_load_cycles",
        "rtl_output_store_cycles",
        "rtl_shift_add_cycles",
        "rtl_noc_reduce_cycles",
    ]
    with top.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=top_fields)
        writer.writeheader()
        for row in ranked[:20]:
            writer.writerow({key: row.get(key, "") for key in top_fields})

    md = out_dir / "rtl_aware_readable_summary.md"
    with md.open("w", encoding="utf-8") as f:
        f.write("# RTL-Aware FLOOD Result Summary\n\n")
        f.write("These numbers use the FLOOD implementation-aware model, not fixed speedup assumptions.\n\n")
        f.write("## Operator Summary\n\n")
        f.write("| Dataset | Operator | Rows | PyTorchSim cycles | FLOOD RTL-aware cycles | FLOOD latency us | Speedup vs PyTorchSim | Utilization |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|---:|\n")
        for row in summary_rows:
            speed = row["speedup_vs_pytorchsim"]
            util = row["weighted_compute_utilization"]
            f.write(
                f"| {row['dataset']} | {row['operator']} | {row['num_rows']} | "
                f"{row['baseline_total_cycles']} | {row['rtl_total_cycles']} | "
                f"{float(row['rtl_latency_us']):.2f} | "
                f"{float(speed):.3f}x | {float(util):.3f} |\n"
            )
        f.write("\n## Top RTL-Aware Cycle Bottlenecks\n\n")
        f.write("| Rank | Dataset | ID | Op | Shape | RTL cycles | Latency us | Utilization |\n")
        f.write("|---:|---|---|---|---|---:|---:|---:|\n")
        for i, row in enumerate(ranked[:10], 1):
            f.write(
                f"| {i} | {row.get('dataset','')} | {row.get('id','')} | {row.get('operator','')} | "
                f"{row.get('shape_args','')} | {int(as_float(row, 'rtl_total_cycles'))} | "
                f"{as_float(row, 'rtl_latency_us'):.2f} | {as_float(row, 'rtl_compute_utilization'):.3f} |\n"
            )

    print("wrote", combined)
    print("wrote", summary)
    print("wrote", top)
    print("wrote", md)


if __name__ == "__main__":
    main()
