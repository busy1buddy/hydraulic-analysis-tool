# Next Instructions — warmup

Quality: BLOCKER

STOP. Before proceeding to Phase 4, fix wave speed regression. (1) In epanet_api.py line 42, change 'wave_speed_ms': 1000 to 1100. (2) In analysis_worker.py line 51, change wave_speed=self.params.get('wave_speed', 1000) to 1100. (3) Add unit test file tests/test_analysis_worker.py with test cases for each analysis type (steady, transient, slurry) and error handling. (4) For slurry parameters: move lazy import to module level (top of analysis_worker.py), parameterize density/roughness via self.params with documented defaults from slurry_solver.py SLURRY_DATABASE, and add comments explaining hardcoded values. (5) Verify scenario_panel correctly handles scenario selection highlighting in the tree. Run full test suite and /review-cycle again before marking complete.
