# RTL Value Repeat Gate

This gate wraps server RTL repeat value checks. A passing row means two separate
RTL executions produced identical numeric outputs for the same tile case.

This is useful repeatability evidence, but it is not an independent software
golden reference. Therefore `direct_paper_ready_cases` remains zero.
