# FLOOD cycle simulator RTL validation

This report compares simulator cycle intervals with direct RTL-clean cases.

## Result

- rtl_clean_cases: 6
- passed_cases: 6
- failed_cases: 0
- pass_rate_percent: 100.0
- max_abs_cycle_error: 0

## Scope

This validates the modeled MAC-machine run timing against direct RTL-clean evidence only.
It does not validate DMA, CPU software control, SRAM data correctness, softmax, sparsity, zero-skip, or large blocked-X workload cases.
