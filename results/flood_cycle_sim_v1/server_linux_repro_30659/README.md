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
- Postprocessor scorecard remained conservative: no paper-ready main-figure rows.
- Main-figure export audits passed.
- `person2_pytorchsim_transformer.csv` was not present on the server, so that workload remains missing evidence rather than being replaced by synthetic data.

Important limitation:

The server run used a minimal source bundle copied to the system disk so that source-manifest and mechanism-profile checks could execute. It proves Linux/server postprocessor reproducibility, but it should not be treated as the full current-RTL source signature for final paper data.
