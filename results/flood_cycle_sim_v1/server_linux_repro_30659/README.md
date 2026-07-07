# Server Linux Reproduction 30659

Server: `root@connect.westc.seetacloud.com:30659`

System-disk working directory: `/root/hpca_simulator/FLOOD_postproc`

Git branch/commit: `simulator` / `ca76a88`

Command:

```bash
bash flood_local/run_flood_cycle_sim.sh
```

Result:

- Linux runner completed successfully on the server.
- RTL/source bundle verification passed before the Linux runner:
  - checked files: `185`
  - failed files: `0`
  - bundle signature: `47d35bd34fdb13cabbd0243b301f0bf3dce7c739448e3322ce70504c03c46937`
- Postprocessor scorecard remained conservative: no paper-ready main-figure rows.
- Main-figure export audits passed.
- `person2_pytorchsim_transformer.csv` was not present on the server, so that workload remains missing evidence rather than being replaced by synthetic data.

Important limitation:

The server run used the generated minimal source bundle copied to the system disk so that source-manifest and mechanism-profile checks could execute. The bundle is now manifest-checked, but it is still not the full RTL repository. It proves Linux/server postprocessor reproducibility, not full RTL simulation completeness.
