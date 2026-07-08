# RTL Calibrated Projection v2

This projection prefers clean P1 large-tile RTL evidence when available and
falls back to clean P0 safe-tile evidence otherwise.

It is more conservative than the original P0-only projection for rows where P1
evidence exists. It is still not direct paper data because it is not full-chip
timing and lacks independent software golden value checks.
