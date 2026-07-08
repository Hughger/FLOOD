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
- Linux runner now automatically verifies the RTL/source bundle before source-profile gates:
  - checked files: `185`
  - failed files: `0`
  - bundle signature: `47d35bd34fdb13cabbd0243b301f0bf3dce7c739448e3322ce70504c03c46937`
- Latest scored run used commit: `ab65a99`
- Latest scored result:
  - postprocessor checks: `9`, non-pass checks: `2`
  - readiness: `21/26` strict pass, `80.77%`
- Postprocessor scorecard remained conservative: no paper-ready main-figure rows.
- Main-figure export audits passed.
- `person2_pytorchsim_transformer.csv` was not present on the server, so that workload remains missing evidence rather than being replaced by synthetic data.

Important limitation:

The server run used the generated minimal source bundle copied to the system disk so that source-manifest and mechanism-profile checks could execute. The Linux runner now treats that bundle manifest as an automatic preflight gate. The bundle is still not the full RTL repository, so this proves Linux/server postprocessor reproducibility, not full RTL simulation completeness.
