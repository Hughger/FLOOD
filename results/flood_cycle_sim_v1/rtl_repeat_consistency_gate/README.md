# RTL Repeat Consistency Gate

This gate checks three server-repeat properties for captured P0 tile cases:

- both RTL executions finished cleanly,
- both executions produced identical done-cycle lists,
- both executions produced identical output-file hashes.

The evidence supports repeatability. It is still not independent software
golden evidence and does not make rows direct paper data.
