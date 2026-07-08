# Real Workload RTL Subset Ingest

This directory gates server RTL runs derived from real workload shapes.

Interpretation:

- `rtl_complete_clean`: completed without timeout and produced clean cycle markers.
- `rtl_partial_progress_clean`: timed out after producing clean cycle markers.
- `rtl_timeout_no_output`: timed out before producing usable cycle markers.
- `rtl_x_or_error`: unknown/X values or abnormal return code.

These rows are calibration evidence only. They are not direct paper-data rows
because the current scope is a bounded MAC-wrapper RTL subset, not full-chip
full-layer RTL timing with golden value comparison.
