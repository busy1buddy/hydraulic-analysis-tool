# Next Instructions � Track 1.1 + 1.3 + 2.5 � vis audit, error handling, fire flow wizard

Quality: NEEDS_WORK

Fix the following in priority order:

1. BLOCKER — Move fire flow sweep to QThread: Create a FireFlowSweepWorker (or extend AnalysisWorker) that emits progress signals. Connect progress signal to the progress bar. This is the same pattern already used in analysis_worker.py. The dialog should disable buttons on start and re-enable on finished/error signals.

2. HIGH — Make run_fire_flow raise ValueError instead of returning {'error': ...} when no network is loaded, to match exception-based error handling in the dialog. Or add dict-based error checking in the dialog's _on_run_single — but raising is cleaner and consistent with how the sweep catches exceptions.

3. HIGH — Fix sweep summary to include error count: change line 243 to include errors in the denominator and show '(N errors)' in the summary label when errors > 0.

4. MEDIUM — Add test for invalid node_id in run_fire_flow (nonexistent node, reservoir/tank node) and verify the error message is user-friendly.

5. LOW — Add progress.setValue(len(junctions)) after the sweep loop completes.

After fixes, run full test suite to confirm no regressions.
