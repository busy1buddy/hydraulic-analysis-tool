"""
Water Quality UI Tests
=======================
Tests for the WaterQualityDialog and the three analysis modes:
  - Water Age   : AGE simulation, values in hours, stagnation flag > 24 hrs
  - Chlorine    : CHEMICAL decay, values in mg/L, WSAA 0.2 mg/L compliance
  - Trace       : TRACE from source reservoir, values in %

Runs headlessly via QT_QPA_PLATFORM=offscreen.

Usage:
    QT_QPA_PLATFORM=offscreen python -m pytest tests/test_water_quality_ui.py -v
"""

import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import wntr

from PyQt6.QtWidgets import QApplication

from epanet_api import HydraulicAPI
from desktop.water_quality_dialog import WaterQualityDialog


# ---------------------------------------------------------------------------
# Locate WNTR bundled Net1 example
# ---------------------------------------------------------------------------

def _net1_path():
    wntr_dir = os.path.dirname(wntr.__file__)
    candidates = [
        os.path.join(wntr_dir, 'library', 'networks', 'Net1.inp'),
        os.path.join(wntr_dir, 'networks', 'examples', 'Net1.inp'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "Could not locate Net1.inp in the wntr package. "
        f"Searched: {candidates}"
    )


NET1_PATH = _net1_path()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def qapp():
    """Module-scoped QApplication (reused across all tests)."""
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


@pytest.fixture(scope='module')
def api():
    """HydraulicAPI with Net1 loaded (shared for speed — read-only tests)."""
    _api = HydraulicAPI()
    _api.load_network_from_path(NET1_PATH)
    return _api


@pytest.fixture
def dialog_age(qapp, api):
    """WaterQualityDialog opened in age mode."""
    dlg = WaterQualityDialog(api, canvas=None, mode='age', parent=None)
    yield dlg
    dlg.close()
    qapp.processEvents()


@pytest.fixture
def dialog_chlorine(qapp, api):
    """WaterQualityDialog opened in chlorine mode."""
    dlg = WaterQualityDialog(api, canvas=None, mode='chlorine', parent=None)
    yield dlg
    dlg.close()
    qapp.processEvents()


@pytest.fixture
def dialog_trace(qapp, api):
    """WaterQualityDialog opened in trace mode."""
    dlg = WaterQualityDialog(api, canvas=None, mode='trace', parent=None)
    yield dlg
    dlg.close()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# 1. Dialog construction
# ---------------------------------------------------------------------------

class TestDialogConstruction:
    def test_age_dialog_creates_without_crash(self, dialog_age):
        """Dialog must create without raising an exception."""
        assert dialog_age is not None

    def test_chlorine_dialog_creates_without_crash(self, dialog_chlorine):
        assert dialog_chlorine is not None

    def test_trace_dialog_creates_without_crash(self, dialog_trace):
        assert dialog_trace is not None

    def test_correct_tab_selected_age(self, dialog_age, qapp):
        qapp.processEvents()
        assert dialog_age.tabs.currentIndex() == 0

    def test_correct_tab_selected_chlorine(self, dialog_chlorine, qapp):
        qapp.processEvents()
        assert dialog_chlorine.tabs.currentIndex() == 1

    def test_correct_tab_selected_trace(self, dialog_trace, qapp):
        qapp.processEvents()
        assert dialog_trace.tabs.currentIndex() == 2

    def test_default_chlorine_initial_conc(self, dialog_chlorine):
        """Default initial concentration must be 0.5 mg/L."""
        assert dialog_chlorine.cl_init_spin.value() == pytest.approx(0.5)

    def test_default_chlorine_bulk_coeff(self, dialog_chlorine):
        """Default bulk decay coefficient must be -0.5/hr."""
        assert dialog_chlorine.cl_bulk_spin.value() == pytest.approx(-0.5)

    def test_default_chlorine_wall_coeff(self, dialog_chlorine):
        """Default wall decay coefficient must be -0.01 m/hr."""
        assert dialog_chlorine.cl_wall_spin.value() == pytest.approx(-0.01)

    def test_trace_source_combo_populated(self, dialog_trace):
        """Trace combo must contain at least one reservoir or tank entry."""
        assert dialog_trace.trace_source_combo.count() >= 1

    def test_show_canvas_btn_initially_disabled(self, dialog_age):
        """Show on Canvas button must be disabled before analysis runs."""
        assert not dialog_age.show_canvas_btn.isEnabled()


# ---------------------------------------------------------------------------
# 2. Water Age mode
# ---------------------------------------------------------------------------

class TestWaterAgeMode:
    def test_age_run_produces_results(self, dialog_age, qapp):
        """Running age analysis must populate the results table."""
        dialog_age._run_age()
        qapp.processEvents()
        assert dialog_age.results_table.rowCount() > 0

    def test_age_values_in_hours(self, dialog_age, qapp):
        """All 'Max Age (hrs)' values must be >= 0 (unit is hours)."""
        dialog_age._run_age()
        qapp.processEvents()
        table = dialog_age.results_table
        for row in range(table.rowCount()):
            val_item = table.item(row, 1)
            assert val_item is not None, f"Row {row} col 1 is None"
            val = float(val_item.text().replace(' hrs', ''))
            assert val >= 0.0, f"Age value {val} is negative at row {row}"

    def test_age_values_positive(self, dialog_age, qapp):
        """Max age values should be > 0 in a running network (Net1 has demand)."""
        dialog_age._run_age()
        qapp.processEvents()
        table = dialog_age.results_table
        max_vals = []
        for row in range(table.rowCount()):
            max_vals.append(float(table.item(row, 1).text().replace(' hrs', '')))
        # At least one junction must have non-zero age
        assert any(v > 0 for v in max_vals), "All water age values are 0"

    def test_age_status_column_exists(self, dialog_age, qapp):
        """Status column (col 3) must be present and non-empty."""
        dialog_age._run_age()
        qapp.processEvents()
        table = dialog_age.results_table
        assert table.columnCount() == 4
        for row in range(table.rowCount()):
            item = table.item(row, 3)
            assert item is not None
            assert item.text() in ("OK", "STAGNATION RISK")

    def test_age_covers_all_junctions(self, api, dialog_age, qapp):
        """Results table row count must match network junction count."""
        dialog_age._run_age()
        qapp.processEvents()
        n_junctions = len(api.wn.junction_name_list)
        assert dialog_age.results_table.rowCount() == n_junctions

    def test_age_summary_updated(self, dialog_age, qapp):
        """Summary label must be non-empty after analysis."""
        dialog_age._run_age()
        qapp.processEvents()
        assert dialog_age.summary_label.text() != ""

    def test_age_stagnation_threshold_24hrs(self, dialog_age, qapp):
        """Junctions with max age > 24 hrs must be labelled STAGNATION RISK."""
        dialog_age._run_age()
        qapp.processEvents()
        table = dialog_age.results_table
        for row in range(table.rowCount()):
            max_age = float(table.item(row, 1).text().replace(' hrs', '').replace(' mg/L', '').replace(' %', ''))
            status = table.item(row, 3).text()
            if max_age > 24.0:
                assert status == "STAGNATION RISK", (
                    f"Junction {table.item(row, 0).text()} age={max_age:.1f} hrs "
                    f"expected STAGNATION RISK but got '{status}'"
                )
            else:
                assert status == "OK"


# ---------------------------------------------------------------------------
# 3. Chlorine Decay mode
# ---------------------------------------------------------------------------

class TestChlorineDecayMode:
    def test_chlorine_run_produces_results(self, dialog_chlorine, qapp):
        """Running chlorine analysis must populate the results table."""
        dialog_chlorine._run_chlorine()
        qapp.processEvents()
        assert dialog_chlorine.results_table.rowCount() > 0

    def test_chlorine_values_in_mgl(self, dialog_chlorine, qapp):
        """All min concentration values must be between 0 and initial_conc."""
        dialog_chlorine._run_chlorine()
        qapp.processEvents()
        table = dialog_chlorine.results_table
        init_conc = dialog_chlorine.cl_init_spin.value()
        for row in range(table.rowCount()):
            val = float(table.item(row, 1).text())
            assert 0.0 <= val <= init_conc + 0.001, (
                f"Min chlorine {val} mg/L out of range [0, {init_conc}]"
            )

    def test_chlorine_values_positive_or_zero(self, dialog_chlorine, qapp):
        """Chlorine concentrations must be >= 0 (no negative concentrations)."""
        dialog_chlorine._run_chlorine()
        qapp.processEvents()
        table = dialog_chlorine.results_table
        for row in range(table.rowCount()):
            for col in (1, 2):
                val = float(table.item(row, col).text())
                assert val >= 0.0, f"Negative chlorine at row {row}, col {col}: {val}"

    def test_chlorine_unit_label_mgl(self, dialog_chlorine, qapp):
        """Column headers must reference mg/L for chlorine."""
        dialog_chlorine._run_chlorine()
        qapp.processEvents()
        header_labels = [
            dialog_chlorine.results_table.horizontalHeaderItem(c).text()
            for c in range(dialog_chlorine.results_table.columnCount())
        ]
        assert any("mg/L" in h for h in header_labels), (
            f"No mg/L unit in headers: {header_labels}"
        )

    def test_chlorine_status_column_exists(self, dialog_chlorine, qapp):
        """Status column must be 'OK' or '< 0.2 mg/L FAIL'."""
        dialog_chlorine._run_chlorine()
        qapp.processEvents()
        table = dialog_chlorine.results_table
        for row in range(table.rowCount()):
            status = table.item(row, 3).text()
            assert status in ("OK", "< 0.2 mg/L FAIL"), (
                f"Unexpected status '{status}' at row {row}"
            )

    def test_chlorine_wsaa_threshold_enforced(self, dialog_chlorine, qapp):
        """Junctions with min < 0.2 mg/L must have FAIL status."""
        dialog_chlorine._run_chlorine()
        qapp.processEvents()
        table = dialog_chlorine.results_table
        for row in range(table.rowCount()):
            min_c = float(table.item(row, 1).text())
            status = table.item(row, 3).text()
            if min_c < 0.2:
                assert status == "< 0.2 mg/L FAIL", (
                    f"Min={min_c:.3f} mg/L expected FAIL but got '{status}'"
                )

    def test_chlorine_covers_all_junctions(self, api, dialog_chlorine, qapp):
        """Row count must match junction count."""
        dialog_chlorine._run_chlorine()
        qapp.processEvents()
        assert dialog_chlorine.results_table.rowCount() == len(api.wn.junction_name_list)

    def test_chlorine_summary_updated(self, dialog_chlorine, qapp):
        dialog_chlorine._run_chlorine()
        qapp.processEvents()
        assert dialog_chlorine.summary_label.text() != ""

    def test_chlorine_high_initial_produces_higher_avg(self, qapp, api):
        """Higher initial concentration should produce higher average values."""
        # Run with default 0.5 mg/L initial
        dlg_low = WaterQualityDialog(api, canvas=None, mode='chlorine')
        dlg_low.cl_init_spin.setValue(0.5)
        dlg_low._run_chlorine()
        qapp.processEvents()
        table_low = dlg_low.results_table
        avg_low = sum(
            float(table_low.item(r, 2).text())
            for r in range(table_low.rowCount())
        ) / max(table_low.rowCount(), 1)
        dlg_low.close()

        # Run with 2.0 mg/L initial
        dlg_high = WaterQualityDialog(api, canvas=None, mode='chlorine')
        dlg_high.cl_init_spin.setValue(2.0)
        dlg_high._run_chlorine()
        qapp.processEvents()
        table_high = dlg_high.results_table
        avg_high = sum(
            float(table_high.item(r, 2).text())
            for r in range(table_high.rowCount())
        ) / max(table_high.rowCount(), 1)
        dlg_high.close()

        assert avg_high > avg_low, (
            f"Higher initial conc should give higher avg: "
            f"avg_low={avg_low:.3f}, avg_high={avg_high:.3f}"
        )


# ---------------------------------------------------------------------------
# 4. Trace mode
# ---------------------------------------------------------------------------

class TestTraceMode:
    def test_trace_run_produces_results(self, dialog_trace, qapp):
        """Running trace analysis must populate the results table."""
        dialog_trace._run_trace()
        qapp.processEvents()
        assert dialog_trace.results_table.rowCount() > 0

    def test_trace_values_in_percent(self, dialog_trace, qapp):
        """All trace percentage values must be between 0 and 100."""
        dialog_trace._run_trace()
        qapp.processEvents()
        table = dialog_trace.results_table
        for row in range(table.rowCount()):
            for col in (1, 2, 3):  # Min%, Avg%, Max%
                val = float(table.item(row, col).text())
                assert 0.0 <= val <= 100.0, (
                    f"Trace % value {val} out of range at row {row}, col {col}"
                )

    def test_trace_unit_label_percent(self, dialog_trace, qapp):
        """Column headers must reference % for trace."""
        dialog_trace._run_trace()
        qapp.processEvents()
        header_labels = [
            dialog_trace.results_table.horizontalHeaderItem(c).text()
            for c in range(dialog_trace.results_table.columnCount())
        ]
        assert any("%" in h for h in header_labels), (
            f"No % unit in headers: {header_labels}"
        )

    def test_trace_four_columns(self, dialog_trace, qapp):
        """Trace table must have 4 columns: Junction, Min%, Avg%, Max%."""
        dialog_trace._run_trace()
        qapp.processEvents()
        assert dialog_trace.results_table.columnCount() == 4

    def test_trace_covers_all_junctions(self, api, dialog_trace, qapp):
        """Row count must match junction count."""
        dialog_trace._run_trace()
        qapp.processEvents()
        assert dialog_trace.results_table.rowCount() == len(api.wn.junction_name_list)

    def test_trace_max_ge_avg_ge_min(self, dialog_trace, qapp):
        """For each junction, Max% >= Avg% >= Min%."""
        dialog_trace._run_trace()
        qapp.processEvents()
        table = dialog_trace.results_table
        for row in range(table.rowCount()):
            junc = table.item(row, 0).text()
            min_p = float(table.item(row, 1).text())
            avg_p = float(table.item(row, 2).text())
            max_p = float(table.item(row, 3).text())
            assert max_p >= avg_p - 0.01, (
                f"{junc}: max {max_p} < avg {avg_p}"
            )
            assert avg_p >= min_p - 0.01, (
                f"{junc}: avg {avg_p} < min {min_p}"
            )

    def test_trace_summary_references_source(self, dialog_trace, qapp):
        """Summary label must mention the source node."""
        dialog_trace._run_trace()
        qapp.processEvents()
        source = dialog_trace.trace_source_combo.currentText().split()[0]
        assert source in dialog_trace.summary_label.text()


# ---------------------------------------------------------------------------
# 5. API methods directly (no UI)
# ---------------------------------------------------------------------------

class TestAPIWaterQualityMethods:
    def test_run_water_quality_age_returns_dict(self, api):
        r = api.run_water_quality(parameter='age', duration_hrs=24, save_plot=False)
        assert 'junction_quality' in r
        assert 'stagnation_risk' in r
        assert 'compliance' in r

    def test_run_water_quality_age_hours_gt_zero(self, api):
        r = api.run_water_quality(parameter='age', duration_hrs=48, save_plot=False)
        jq = r['junction_quality']
        assert len(jq) > 0
        for junc, vals in jq.items():
            assert vals['max_age_hrs'] >= 0, f"{junc} max_age_hrs < 0"
            assert vals['avg_age_hrs'] >= 0, f"{junc} avg_age_hrs < 0"

    def test_run_water_quality_chlorine_returns_dict(self, api):
        r = api.run_water_quality_chlorine(
            initial_conc=0.5, bulk_coeff=-0.5, wall_coeff=-0.01,
            duration_hrs=24, save_plot=False
        )
        assert 'junction_quality' in r
        assert 'non_compliant' in r
        assert 'compliance' in r
        assert r['unit'] == 'mg/L'

    def test_run_water_quality_chlorine_values_nonnegative(self, api):
        r = api.run_water_quality_chlorine(
            initial_conc=0.5, bulk_coeff=-0.5, wall_coeff=-0.01,
            duration_hrs=24, save_plot=False
        )
        for junc, vals in r['junction_quality'].items():
            assert vals['min_conc'] >= 0, f"{junc} min_conc < 0"
            assert vals['avg_conc'] >= 0, f"{junc} avg_conc < 0"

    def test_run_water_quality_chlorine_unit_is_mgl(self, api):
        r = api.run_water_quality_chlorine(save_plot=False)
        assert r.get('unit') == 'mg/L'

    def test_run_water_quality_trace_returns_dict(self, api):
        reservoir = api.wn.reservoir_name_list[0]
        r = api.run_water_quality_trace(
            source_node=reservoir, duration_hrs=24, save_plot=False
        )
        assert 'junction_quality' in r
        assert 'source_node' in r
        assert r['unit'] == '%'

    def test_run_water_quality_trace_values_0_to_100(self, api):
        reservoir = api.wn.reservoir_name_list[0]
        r = api.run_water_quality_trace(
            source_node=reservoir, duration_hrs=24, save_plot=False
        )
        for junc, vals in r['junction_quality'].items():
            for key in ('min_pct', 'avg_pct', 'max_pct'):
                assert 0.0 <= vals[key] <= 100.0, (
                    f"{junc} {key}={vals[key]} out of [0, 100]"
                )

    def test_run_water_quality_trace_unit_is_percent(self, api):
        reservoir = api.wn.reservoir_name_list[0]
        r = api.run_water_quality_trace(source_node=reservoir, save_plot=False)
        assert r.get('unit') == '%'

    def test_no_network_age_returns_error(self):
        empty_api = HydraulicAPI()
        r = empty_api.run_water_quality(parameter='age', save_plot=False)
        assert 'error' in r

    def test_no_network_chlorine_returns_error(self):
        empty_api = HydraulicAPI()
        r = empty_api.run_water_quality_chlorine(save_plot=False)
        assert 'error' in r

    def test_no_network_trace_returns_error(self):
        empty_api = HydraulicAPI()
        r = empty_api.run_water_quality_trace(source_node='R1', save_plot=False)
        assert 'error' in r

    def test_original_settings_restored_after_age(self, api):
        """run_water_quality must restore duration and quality param."""
        original_duration = api.wn.options.time.duration
        original_param = api.wn.options.quality.parameter
        api.run_water_quality(parameter='age', duration_hrs=48, save_plot=False)
        assert api.wn.options.time.duration == original_duration
        assert api.wn.options.quality.parameter == original_param

    def test_original_settings_restored_after_chlorine(self, api):
        """run_water_quality_chlorine must restore duration and quality param."""
        original_duration = api.wn.options.time.duration
        original_param = api.wn.options.quality.parameter
        api.run_water_quality_chlorine(duration_hrs=24, save_plot=False)
        assert api.wn.options.time.duration == original_duration
        assert api.wn.options.quality.parameter == original_param

    def test_original_settings_restored_after_trace(self, api):
        """run_water_quality_trace must restore duration and quality param."""
        original_duration = api.wn.options.time.duration
        original_param = api.wn.options.quality.parameter
        reservoir = api.wn.reservoir_name_list[0]
        api.run_water_quality_trace(source_node=reservoir, duration_hrs=24, save_plot=False)
        assert api.wn.options.time.duration == original_duration
        assert api.wn.options.quality.parameter == original_param
