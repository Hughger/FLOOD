# FLOOD Timeline Consistency Report

This report checks internal consistency of generated cycle timelines. It does
not prove RTL correctness, but it catches broken interval accounting before
paper data is exported.

Generated files:

- `timeline_checks.csv`: per-workload interval checks.
- `timeline_summary.csv`: pass/fail counts.

Rule: `failed_rows` must be 0 before generated cycle tables are used.
