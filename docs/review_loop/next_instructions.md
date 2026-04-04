# Next Instructions � formula and standards audit

Quality: NEEDS_WORK

Fix the two HIGH issues before proceeding:

1. epanet_api.py line 42: Change default wave_speed_ms from 1000 to 1100. Add comment: '# AS 2280 minimum for ductile iron — conservative default'. Verify lines 930, 1123, 1169 still work correctly with the new default.

2. slurry_solver.py herschel_bulkley_headloss() around line 245: Change laminar friction from f=16/Re to f=64/Re (Darcy convention) to match bingham_plastic_headloss(). Update the comment to explicitly state Darcy convention. Check the turbulent branch for the same issue — if it uses Dodge-Metzner (which returns Fanning), multiply by 4 before feeding to Darcy-Weisbach.

3. Add four missing tests: (a) zero-diameter pipe returns no velocity error, (b) fire flow flags nodes below 12m residual, (c) WSAA flags nodes above 50m, (d) transient compliance subtracts elevation before PN comparison.

4. In pipe_stress.py line 116, add comment: '# Lower-bound value per AS/NZS 4130 Table 2 — conservative for burst design'.

Run full test suite after each fix to confirm no regressions.
