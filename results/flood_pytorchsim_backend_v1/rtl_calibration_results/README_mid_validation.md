# RTL Mid-size Validation Notes

These cases validate whether the 21-case bring-up formula extrapolates to larger
`cout` and `cin_idx_total`.

| case | status | observed cycles | interpretation |
|---|---|---:|---|
| `m01_k1_c10_g4_ci10` | complete | `1493 = 9*149 + 152` | Matches the bring-up formula for `k=1`, `cout=10`, `cin=10`. |
| `m02_k3_c10_g4_ci10` | partial timeout | `7*562` completed before timeout | Superseded by the complete run below. |
| `m02_k3_c10_g4_ci10_complete` | complete | `5623 = 9*562 + 565` | Matches the bring-up formula for `k=3`, `cout=10`, `cin=10`. |

The first spatial-conv attempt timed out because RTL simulation is slow, not
because the RTL stopped progressing. The repeated complete run finished all ten
runs and confirmed the predicted total of 5623 cycles.

Conclusion: the workload-level extrapolation is pessimistic but consistent with
the current RTL testbench behavior. It still should not be treated as final paper
data until representative full-layer RTL runs or a faster simulator flow are
available.
