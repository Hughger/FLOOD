# Server Linux Reproduction 30659

Server: `root@connect.westc.seetacloud.com:30659`

System-disk working directory: `/root/hpca_simulator/FLOOD_postproc`

Git branch/commit: `simulator` / `388e0ee`

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
- Latest scored run used commit: `388e0ee`
- Latest scored result:
  - postprocessor checks: `11`, non-pass checks: `2`
  - readiness: `23/28` strict pass, `82.14%`
- HPCA figure contract evidence was generated on the server:
  - figures tracked: `8`
  - paper-ready figures: `0`
  - final-gate-ready rows: `0`
  - policy: `not_ready_for_direct_paper_plotting`
  - note: the server run is more conservative than the local run because the server does not carry the local legacy/workload-composition helper outputs; those missing inputs are not silently substituted.
- Source-bundle tamper audit is now part of the score/readiness evidence:
  - normal server auto-verify: `185/0 pass`
  - adversarial tamper verify: `1` changed source file rejected as expected
- Postprocessor scorecard remained conservative: no paper-ready main-figure rows.
- Main-figure export audits passed.
- `person2_pytorchsim_transformer.csv` was not present on the server, so that workload remains missing evidence rather than being replaced by synthetic data.

Important limitation:

The server run used the generated minimal source bundle copied to the system disk so that source-manifest and mechanism-profile checks could execute. The Linux runner now treats that bundle manifest as an automatic preflight gate. The bundle is still not the full RTL repository, so this proves Linux/server postprocessor reproducibility, not full RTL simulation completeness.

For the `388e0ee` run, the server could not fetch GitHub directly because outbound HTTPS to GitHub timed out. I verified the already-pushed commit by transferring a local `git archive` of `388e0ee` to the server and running the Linux regression from that archive.
