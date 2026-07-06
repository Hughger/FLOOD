# FLOOD cycle simulator RTL validation

This report compares simulator cycle intervals with direct RTL-clean cases.

## Result

- rtl_clean_cases: 6
- passed_cases: 6
- failed_cases: 0
- direct_blocked_cases: 5
- blocked_x_cases: 5
- blocked_zero_cycle_cases: 1
- pass_rate_percent: 100.0
- max_abs_cycle_error: 0

## Scope

This validates the modeled MAC-machine run timing against direct RTL-clean evidence only.
Blocked direct RTL attempts are listed separately and excluded from paper main performance tables.
It does not validate DMA, CPU software control, SRAM data correctness, softmax, sparsity, or zero-skip.
