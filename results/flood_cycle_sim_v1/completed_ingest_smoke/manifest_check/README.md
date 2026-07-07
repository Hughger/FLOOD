# FLOOD RTL Task Manifest Check

This report checks whether RTL task manifests are ready to feed into the
system/value/final gates.

Draft manifests are expected to fail because they contain `PATH_TO_*`
placeholders. After real RTL logs and output files are collected, rerun this
check; only `ready_for_gate_ingestion` tasks should enter paper-data gates.
