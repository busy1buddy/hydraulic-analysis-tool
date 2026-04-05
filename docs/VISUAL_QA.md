# Visual QA Walkthrough — v2.9.0 → v3.0.0-rc1

**Date:** 2026-04-05
**Performed by:** Automated (offscreen Qt) + code inspection
**Limitation:** No human eye on a rendered window. All checks are
**functional and data-flow correctness**. Visual polish items
(cramped layout, font weight, colour contrast, icon alignment)
require a human review session.

---

## How this QA was done

All 10 steps run programmatically via
`tests/test_visual_qa_walkthrough.py` using
`QT_QPA_PLATFORM=offscreen`. Each step instantiates the real
`MainWindow`, real dialogs, and real API methods. Signal emissions,
dialog outputs, file creation, and data shapes are verified — but no
pixels are rendered to a display.

**Gap:** Anything that looks ugly, cramped, misaligned, or unclear
visually will not be caught here. Schedule a 30-minute human session
before public release.

---

## Step-by-step results

| # | Step | Result | Notes |
|---|---|---|---|
| 1 | App launches | **PASS** | Title, 7 menus, status bar, central widget, 1400×900 |
| 2 | Load demo_network | **PASS** | 10 junctions, 11 pipes, reservoir R1 loaded |
| 3 | F5 steady-state | **PASS** | Returns pressures, 3 WSAA violations, quality score ~65/100 |
| 4 | Operations Dashboard | **PASS** | `status_light` = red/amber/green, KPIs populated |
| 5 | Root Cause Analysis | **PASS** | Correctly identifies J9 + J10 low pressure, fix options with AUD costs |
| 6 | Slurry mode (mining tutorial) | **PASS** | Durand + Wasp critical velocities computed per-pipe |
| 7 | Safety Case Report dialog | **PASS** | Engineer field, verdict colour-coded, JSON export valid |
| 8 | What-If slider 150% | **PASS** | Signal fires, pressures update, low-pressure count increases |
| 9 | GeoJSON export | **PASS** | 22 features (11 nodes + 11 pipes), valid JSON, WSAA status properties |
| 10 | DOCX report | **PASS** | File >5 KB, contains Summary/Executive/Overview headings |

**10/10 functional steps PASS.**

---

## Polish issues found (fixed in this session)

### Fixed: Window title had no version number

**Before:** `"Hydraulic Analysis Tool"` — looks like a dev build.
**After:** `"Hydraulic Analysis Tool — v2.9.0"`
Applies to all 7 title-update sites including post-file-open titles.

### Fixed: Empty status bar on startup

**Before:** `currentMessage()` was empty string. The permanent
widgets (Nodes: 0, Pipes: 0, WSAA: --) were there, but the main
status text was silent. First-time users have no prompt.
**After:** `"Ready — open a network (File > Open, Ctrl+O) or
Help > Run Demo to start."`

### Fixed: About dialog showed v1.0

**Before:** `"Hydraulic Analysis Tool v1.0\n\n"` — outdated.
**After:** `"Hydraulic Analysis Tool v2.9.0\n\n"`

---

## Polish issues NOT fixed (need human judgment)

Logged to `docs/blockers.md`:

1. **Slurry mode discoverability.** The QA checklist asked to "check
   the slurry checkbox" but there is no top-level slurry checkbox —
   slurry is only accessible via `Analysis > Slurry Mode`. Consider
   adding a visible status indicator in the toolbar or status bar when
   slurry mode is active.

2. **No explicit "Run Demo" completion feedback.** The demo
   concludes with a popup, but during the four-step QTimer chain
   (500 ms apart) the user sees status-bar updates only. Consider a
   progress dialog with a visible step counter for clarity.

3. **Status-bar permanent widgets show `--` on startup.** Looks
   slightly unprofessional until a network is loaded. Alternative
   display: hide these widgets until a network is loaded, or show
   `(load network)` instead of `--`.

4. **Font-metric warning on headless runs** —
   `QFontDatabase: Cannot find font directory`. This is a PyQt6
   installation issue on Windows, not a tool bug. Harmless in
   production but noisy in CI logs.

5. **DEMO_SCRIPT Act 2.5 code examples reference `api.find_best_upgrade().top_5`
   as attribute access** — actually it's dict-key access
   `api.find_best_upgrade()['top_5']`. Minor script doc error.

---

## What was NOT verified (need human QA session)

- **Layout and cramping:** I cannot tell if dock panels overlap, if
  the canvas is too small to be usable, or if labels wrap awkwardly
  at 1400×900.
- **Colour choices:** The WSAA pass/fail colour coding may be
  confusing to colour-blind users. No audit performed.
- **Dark mode compatibility:** Unknown whether the app respects
  system dark-mode settings.
- **DPI scaling:** Behaviour at 150% / 200% Windows scaling unknown.
- **Drag-and-drop of .inp files:** The hook exists
  (`setAcceptDrops(True)`) but the drop handler is not tested
  headlessly.
- **PyQtGraph canvas rendering:** Zoom, pan, element selection, and
  colourmap legends are not verified.
- **Error dialogs:** Their wording, button layouts, and Escape
  behaviour are tested, but visual layout isn't.

---

## Recommended human QA checklist (30 minutes)

Before v3.0.0 public release:

1. Launch `python main_app.py` on Windows with default Qt theme.
2. Drag-and-drop `tutorials/demo_network/network.inp` onto the window.
3. Verify canvas renders the network with visible nodes and pipes.
4. Press F5; verify WSAA colours update on the canvas.
5. Open each dialog from every menu — confirm no overlap, no
   cut-off labels, tab order is logical.
6. Resize the window to 1200×800 minimum; confirm nothing gets
   clipped.
7. Test on a 4K / 150%-scaled monitor.
8. Test one workflow end-to-end with a real user who has never
   seen the tool.

---

## Headless QA test

`tests/test_visual_qa_walkthrough.py` (10 tests) is now part of
the test suite. Run anytime with:

```bash
python -m pytest tests/test_visual_qa_walkthrough.py -v
```
