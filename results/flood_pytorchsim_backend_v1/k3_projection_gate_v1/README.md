# k3 projection gate v1

## Purpose

This gate documents the remaining k3 projection rows after fast credibility tightening. Current RTL-clean k3 evidence covers res=1, cin<=3, cout<=6. Workload k3 rows outside that envelope stay in appendix/projection, not the HPCA main table.

## Counts

- appendix_projection_cin_or_cout_extrapolation: 10
- appendix_projection_spatial_extrapolation: 1

## Rule

No k3 workload row is admitted to the main performance table unless it becomes direct RTL-clean. The current rows are useful as projection/diagnostic evidence only.
