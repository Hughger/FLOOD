# FLOOD RTL Source Manifest

This manifest binds simulator evidence to the RTL/Chisel source files that
anchor the current model scope.

Generated files:

- `rtl_source_manifest.csv`: source file paths, sizes, and SHA256 hashes.
- `rtl_source_summary.csv`: source group counts and combined source signature.
- `hardware_source_signature.txt`: combined source signature only.

Policy: if `hardware_source_signature_sha256` changes, old simulator outputs
must not be mixed with newly generated data without rerunning the full gates.
