# FLOOD Simulator Readiness Report

This report is intentionally conservative. It answers one question: can the
current tool be handed to students so that their output CSVs are directly usable
as paper data?

## Summary

- Strict pass: 32/37 requirements (86.49%).
- Usable with caveats: 90.54%.
- Goal status: not complete for HPCA paper data.
- Main blocker: real workload output-value checks and full-chip/system timing calibration.

## What Is Already Solid

- Base FLOOD MAC direct RTL-clean timing is currently all-pass.
- Blocked/X/zero-cycle RTL samples are explicitly separated.
- Paper-use gates exist, so projection rows are not silently mixed into main tables.
- HPCA Fig.1-Fig.8 requirements are now tracked as a machine-checkable contract.
- Six optimization folders are inventoried and remain disabled unless evidence is added.

## What Still Blocks Paper-Ready Batch Runs

- Real workloads still lack pass-grade RTL/golden output-value evidence.
- Full-chip CPU/DMA/control timing is still a smoke/projection path.
- Fig.6/Fig.7/Fig.5 still cannot be directly plotted until real performance,
  mechanism, and quality evidence is ingested.
- Softmax, MACTree, zero-skip, channel-group sparsity, INT8/INT4, and outlier paths
  are inventoried but not validated enough for main performance figures.

## Files

- `readiness_requirements.csv`: per-requirement evidence and blocker table.
- `readiness_summary.csv`: compact pass/partial/missing summary.
