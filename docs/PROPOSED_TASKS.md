# Proposed Tasks for Cycle 6

Based on findings from Cycle 5.

## 1. Results table sort/filter (UX Audit finding)
The UX audit found "find highest velocity pipe" requires 4-5 steps because
results tables have no sorting or filtering. Adding QSortFilterProxyModel
to node_results_table and pipe_results_table would allow:
- Click column header to sort by pressure/velocity/headloss
- Right-click > Filter to show only violations
This would reduce the "find violation" task from 5 steps to 2.

## 2. CSV/Excel export for results tables
The UX audit found no direct export path for results data. Engineers need
to copy-paste from DOCX reports into Excel. Adding a "Export to CSV"
context menu on results tables would enable direct data export.

## 3. DOCX/PDF report slurry support
The slurry display verification found that reports use water values even
in slurry mode. The report generators (docx_report.py, pdf_report.py)
should check for slurry data in the results dict and use slurry headloss
and velocity values when present.
