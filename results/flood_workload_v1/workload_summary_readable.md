# FLOOD Workload V1 Readable Summary

This table summarizes representative proxy workloads for the current PyTorchSim baseline and the first-pass FLOOD post-processing estimate.

Important: the FLOOD numbers below are pipeline-validation estimates. They are not final paper numbers.

| Workload | Operator | Baseline cycles | Baseline latency us | FLOOD est. cycles | FLOOD est. latency us | Speedup |
|---|---|---:|---:|---:|---:|---:|
| SD UNet early conv 64x64 C320 | Conv | 187707 | 199.69 | 155357 | 165.27 | 1.208x |
| SD UNet mid conv 32x32 C640 | Conv | 136456 | 145.17 | 112942 | 120.15 | 1.208x |
| SD UNet late conv 16x16 C1280 | Conv | 294253 | 313.04 | 243536 | 259.08 | 1.208x |
| SD Attention QKV projection | GEMM | 34810 | 37.03 | 27527 | 29.28 | 1.265x |
| SD Attention score GEMM | GEMM | 13070 | 13.90 | 10341 | 11.00 | 1.264x |
| SD Attention softmax | Softmax | 43587 | 46.37 | 30774 | 32.74 | 1.416x |
| VAE decoder conv | Conv | 47318 | 50.34 | 39170 | 41.67 | 1.208x |
| DiT-B/4 projection | GEMM | 10941 | 11.64 | 8658 | 9.21 | 1.264x |
| DiT-B/4 MLP expansion | GEMM | 36396 | 38.72 | 28781 | 30.62 | 1.265x |
| DiT-B/4 attention softmax | Softmax | 4602 | 4.90 | 3258 | 3.47 | 1.413x |

## What This Means

- The PyTorchSim baseline path is now working for Conv, GEMM, Softmax, and a Diffusion smoke workload.
- The representative FLOOD post-processing path is also working end to end.
- Current estimates show the expected trend: Softmax benefits most, GEMM next, Conv modestly.
- The next step should replace these proxy shapes with exact shapes traced from SD v1.5 UNet, VAE Decoder, and DiT.

## Current Limitation

These tests are not yet full end-to-end SD inference. They are representative operator-level tests selected to match FLOOD's target workloads.
