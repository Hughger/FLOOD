# FLOOD Validation Coverage Matrix

This report summarizes which generated workload rows are backed by direct clean
RTL shape evidence, which are projection-only, and which overlap blocked/X
evidence.

Generated files:

- `validation_coverage_detail.csv`: one row per workload.
- `validation_coverage_summary.csv`: aggregate by result directory/operator/evidence bucket.
- `next_rtl_validation_priority.csv`: top rows to run next in full-chip RTL/value validation.
- `coverage_readiness_summary.csv`: compact counts.
