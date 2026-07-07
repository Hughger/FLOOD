# FLOOD mechanism inventory

This inventory compares the six standalone optimization folders against `FLOOD/`.

The result is not an integration patch. It is a gate for simulator work:

- `mechanism_summary.csv`: per-mechanism changed-file counts and simulator hook.
- `mechanism_changed_files.csv`: changed or added files relative to base.
- `mechanism_sim_hooks.csv`: required simulator inputs and evidence gate.
- `mechanism_enable_template.csv`: explicit disabled-by-default mechanism switch template.

Paper policy: all mechanisms remain disabled in main simulator results until RTL timing and output-value evidence is available for the claimed scope.
