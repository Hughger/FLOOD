# Server RTL Repeat Value Inputs

This directory prepares value-check inputs from two server RTL runs of the same
P0 tile cases. The first run is frozen as `golden_values.txt`; the second run is
treated as `rtl_values.txt`.

This proves deterministic RTL output repeatability for the captured tile cases.
It is not an independent software golden reference.
