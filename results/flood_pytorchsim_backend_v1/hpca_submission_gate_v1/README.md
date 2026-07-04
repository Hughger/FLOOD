# HPCA submission data gate v1

## Gate status

- status: PASS
- main table rows: 6
- appendix projection rows: 14
- blocked/excluded rows: 11

## Main-table rule

Only `B_direct_rtl_clean_workload_row` is allowed in the main performance table. C-level rows may be used only in an explicitly labeled projection/appendix table. D-level rows are diagnostic evidence and must not be plotted as valid performance data.

## Files

- `main_table_rows.csv`: direct RTL-clean rows only.
- `appendix_projection_rows.csv`: C-level projection rows only.
- `blocked_or_excluded_rows.csv`: D-level blocked/excluded/boundary rows.
- `gate_summary.csv`: grouped row counts and cycle totals.

## Why this matters

Several direct RTL attempts matched the predicted cycle count but failed XPROBE output validity. This gate prevents those rows from entering the HPCA main performance table by accident.
