# FLOOD PyTorchSim small-loop summary

This is the first pipeline check: PyTorchSim dense baseline plus FLOOD post-processing model.

- gemm_128: baseline 1089 cycles, estimated FLOOD 875 cycles, speedup 1.245x.
- conv_smoke: baseline 54336 cycles, estimated FLOOD 44978 cycles, speedup 1.208x.
- softmax_512: baseline 11804 cycles, estimated FLOOD 8713 cycles, speedup 1.355x.
- diffusion_smoke: baseline 2004846 cycles, estimated FLOOD 1619347 cycles, speedup 1.238x.
