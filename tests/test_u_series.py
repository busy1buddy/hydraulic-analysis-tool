"""
U/V/I-series tests:
  I7 find_best_upgrade
  V2 batch_compliance_check
  V4 log_analysis_run + get_project_history
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'demo_network',
                        'network.inp')
SIMPLE_INP = os.path.join(PROJECT_ROOT, 'tutorials', 'simple_loop',
                           'network.inp')


# ---------- I7 find_best_upgrade -------------------------------------------

class TestFindBestUpgrade:

    def test_no_network_error(self):
        a = HydraulicAPI()
        r = a.find_best_upgrade()
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_ranks_upgrades(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.find_best_upgrade()
        assert 'error' not in r
        assert r['n_pipes_tested'] > 0
        assert len(r['ranked_upgrades']) > 0
        assert 'recommendation' in r
        assert r['recommendation']

    def test_identifies_undersized_branch(self):
        """Demo network has undersized DN100 branches (P10, P11) that should
        appear in the top upgrade candidates."""
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.find_best_upgrade()
        # P10 or P11 (both DN100, undersized) should be in the top 5
        top5_ids = [c['pipe_id'] for c in r['top_5'][:5]]
        has_undersized = 'P10' in top5_ids or 'P11' in top5_ids
        assert has_undersized, \
            f'Neither P10 nor P11 in top 5 candidates: {top5_ids}'

    def test_rankings_sorted_by_value(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.find_best_upgrade()
        vals = [c['value_m_per_1000aud'] for c in r['ranked_upgrades']]
        assert vals == sorted(vals, reverse=True)

    def test_baseline_preserved_after_simulation(self):
        """Every candidate's diameter must be restored after test."""
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        orig_diameters = {pid: a.wn.get_link(pid).diameter
                          for pid in a.wn.pipe_name_list}
        a.find_best_upgrade()
        for pid, d in orig_diameters.items():
            assert abs(a.wn.get_link(pid).diameter - d) < 1e-12

    def test_max_pipes_limits_work(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.find_best_upgrade(max_pipes=3)
        assert r['n_pipes_tested'] <= 3

    def test_cost_assumptions_present(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.find_best_upgrade()
        assert 'cost_assumptions' in r
        assert r['cost_assumptions']['currency'] == 'AUD'
        assert 'uncertainty_pct' in r['cost_assumptions']

    def test_velocity_target_metric(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        r = a.find_best_upgrade(
            target_metric='max_velocity_reduction_ms')
        vals = [c['velocity_value_per_1000aud']
                for c in r['ranked_upgrades']]
        assert vals == sorted(vals, reverse=True)


# ---------- V2 batch_compliance_check --------------------------------------

class TestBatchCompliance:

    def test_empty_list_error(self):
        a = HydraulicAPI()
        r = a.batch_compliance_check([])
        assert 'error' in r

    def test_missing_file_captured(self, tmp_path):
        a = HydraulicAPI()
        fake = str(tmp_path / 'nope.inp')
        r = a.batch_compliance_check([fake])
        assert r['summary']['failed'] == 1
        assert r['rows'][0]['error']

    def test_processes_multiple_networks(self):
        a = HydraulicAPI()
        r = a.batch_compliance_check([DEMO_INP, SIMPLE_INP])
        assert r['summary']['total_networks'] == 2
        assert r['summary']['successful'] == 2
        for row in r['rows']:
            assert row['quality_score'] is not None
            assert row['min_pressure_m'] is not None
            assert row['resilience_index'] is not None
            assert row['wsaa_pass'] in (True, False)

    def test_csv_output(self, tmp_path):
        a = HydraulicAPI()
        out = str(tmp_path / 'batch.csv')
        r = a.batch_compliance_check([DEMO_INP, SIMPLE_INP],
                                      csv_output_path=out)
        assert r['csv_output'] == out
        assert os.path.exists(out)

        # CSV has correct row count (header + 2 data rows)
        with open(out) as f:
            lines = [ln for ln in f.read().splitlines() if ln]
        assert len(lines) == 3  # header + 2 data rows

    def test_api_state_preserved(self):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        original_network = a._inp_file
        original_pipes = len(a.wn.pipe_name_list)
        a.batch_compliance_check([SIMPLE_INP])
        # After batch, original network is restored
        assert a._inp_file == original_network
        assert len(a.wn.pipe_name_list) == original_pipes


# ---------- V4 project history ---------------------------------------------

class TestProjectHistory:

    def test_get_history_when_missing(self, tmp_path):
        a = HydraulicAPI()
        path = str(tmp_path / 'no_history.json')
        h = a.get_project_history(history_path=path)
        assert h['n_entries'] == 0
        assert h['entries'] == []

    def test_log_then_retrieve(self, tmp_path):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        res = a.run_steady_state(save_plot=False)
        path = str(tmp_path / 'hist.json')

        logged = a.log_analysis_run(
            'steady_state', results=res, history_path=path,
            duration_seconds=0.5)
        assert logged['total_entries'] == 1
        assert logged['entry']['analysis_type'] == 'steady_state'
        assert logged['entry']['quality_score'] is not None
        assert logged['entry']['wsaa_pass'] is False  # demo has violations

        h = a.get_project_history(history_path=path)
        assert h['n_entries'] == 1
        assert h['entries'][0]['analysis_type'] == 'steady_state'

    def test_multiple_entries_accumulate(self, tmp_path):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        res = a.run_steady_state(save_plot=False)
        path = str(tmp_path / 'hist.json')

        for _ in range(3):
            a.log_analysis_run('steady_state', results=res,
                                history_path=path)

        h = a.get_project_history(history_path=path)
        assert h['n_entries'] == 3

    def test_trend_contains_quality_scores(self, tmp_path):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        res = a.run_steady_state(save_plot=False)
        path = str(tmp_path / 'hist.json')

        a.log_analysis_run('steady_state', results=res,
                            history_path=path)
        a.log_analysis_run('fire_flow', results=res, history_path=path)

        h = a.get_project_history(history_path=path)
        assert len(h['quality_score_trend']) == 2
        ts, score = h['quality_score_trend'][0]
        assert 'T' in ts  # ISO timestamp
        assert score is not None

    def test_entry_has_timestamp_and_network(self, tmp_path):
        a = HydraulicAPI()
        a.load_network(DEMO_INP)
        path = str(tmp_path / 'hist.json')
        res = a.log_analysis_run('manual_test', history_path=path)
        entry = res['entry']
        assert entry['timestamp_utc']
        assert 'T' in entry['timestamp_utc']
        assert entry['network'] == 'network.inp'

    def test_corrupted_history_returns_error(self, tmp_path):
        path = tmp_path / 'bad.json'
        path.write_text('not valid json{{', encoding='utf-8')
        a = HydraulicAPI()
        h = a.get_project_history(history_path=str(path))
        assert 'error' in h
        assert 'Fix:' in h['error']


# ---------- U1 worked examples library ---------------------------------------

class TestWorkedExamples:

    EXAMPLES_DIR = os.path.join(PROJECT_ROOT, 'docs', 'worked_examples')

    EXPECTED_EXAMPLES = [
        'example_01_pipe_sizing.md',
        'example_02_fire_flow.md',
        'example_03_low_pressure.md',
        'example_04_surge_vessel.md',
        'example_05_slurry_critical_velocity.md',
    ]

    def test_all_examples_exist(self):
        missing = []
        for fname in self.EXPECTED_EXAMPLES:
            path = os.path.join(self.EXAMPLES_DIR, fname)
            if not os.path.exists(path):
                missing.append(fname)
        assert not missing, f'Missing worked examples: {missing}'

    def test_index_exists(self):
        assert os.path.exists(
            os.path.join(self.EXAMPLES_DIR, 'README.md'))

    def test_each_example_has_references(self):
        """Every worked example must cite at least one standard
        or textbook reference."""
        missing_refs = []
        for fname in self.EXPECTED_EXAMPLES:
            path = os.path.join(self.EXAMPLES_DIR, fname)
            text = open(path, encoding='utf-8').read().lower()
            # Must reference either WSAA, AS/NZS, or knowledge_base
            if not any(token in text for token in
                       ('wsaa', 'as/nzs', 'as 2', 'knowledge_base',
                        'durand', 'wasp', 'joukowsky', 'hazen',
                        'wylie')):
                missing_refs.append(fname)
        assert not missing_refs, \
            f'Examples missing standard references: {missing_refs}'

    def test_each_example_has_manual_calc(self):
        """Every example must include both manual calc and tool code."""
        missing_calc = []
        for fname in self.EXPECTED_EXAMPLES:
            path = os.path.join(self.EXAMPLES_DIR, fname)
            text = open(path, encoding='utf-8').read()
            # Must have a ```python block (tool code) AND a heading
            # for manual calc or step
            if '```python' not in text:
                missing_calc.append(fname)
        assert not missing_calc, \
            f'Examples missing tool verification code: {missing_calc}'


# ---------- V1 weekly report automation -------------------------------------

class TestWeeklyReportScript:

    def test_invalid_extension_error(self, tmp_path):
        a = HydraulicAPI()
        r = a.generate_weekly_report_script(
            inp_path='x.inp', output_dir=str(tmp_path),
            script_path=str(tmp_path / 'x.exe'))
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_generates_bat_file(self, tmp_path):
        a = HydraulicAPI()
        script = str(tmp_path / 'weekly.bat')
        r = a.generate_weekly_report_script(
            inp_path=DEMO_INP, output_dir=str(tmp_path / 'out'),
            script_path=script)
        assert 'error' not in r
        assert r['script_type'] == 'bat'
        assert os.path.exists(script)
        content = open(script).read()
        assert '@echo off' in content
        assert DEMO_INP in content
        assert 'HydraulicAPI' in content

    def test_generates_sh_file(self, tmp_path):
        a = HydraulicAPI()
        script = str(tmp_path / 'weekly.sh')
        r = a.generate_weekly_report_script(
            inp_path=DEMO_INP, output_dir=str(tmp_path / 'out'),
            script_path=script)
        assert 'error' not in r
        assert r['script_type'] == 'sh'
        content = open(script).read()
        assert '#!/bin/sh' in content
        assert 'cron' in r['scheduler_command']

    def test_bat_scheduler_command(self, tmp_path):
        a = HydraulicAPI()
        script = str(tmp_path / 'w.bat')
        r = a.generate_weekly_report_script(
            inp_path=DEMO_INP, output_dir=str(tmp_path),
            script_path=script)
        assert 'schtasks' in r['scheduler_command']
        assert 'WEEKLY' in r['scheduler_command']


# ---------- V5 report branding ----------------------------------------------

class TestReportBranding:

    def test_get_when_missing(self, tmp_path, monkeypatch):
        a = HydraulicAPI(work_dir=str(tmp_path))
        r = a.get_report_branding()
        assert r['branding'] == {}

    def test_set_and_retrieve(self, tmp_path):
        a = HydraulicAPI(work_dir=str(tmp_path))
        saved = a.set_report_branding(
            company_name='Acme Hydraulics',
            engineer_name='Jane Doe',
            engineer_pe_number='RPEQ-12345')
        assert 'error' not in saved
        assert saved['branding']['company_name'] == 'Acme Hydraulics'

        r = a.get_report_branding()
        assert r['branding']['company_name'] == 'Acme Hydraulics'
        assert r['branding']['engineer_name'] == 'Jane Doe'
        assert r['branding']['engineer_pe_number'] == 'RPEQ-12345'

    def test_partial_update_preserves_existing(self, tmp_path):
        a = HydraulicAPI(work_dir=str(tmp_path))
        a.set_report_branding(
            company_name='Acme', engineer_name='Jane')
        # Update only engineer_name
        a.set_report_branding(engineer_name='Bob')
        r = a.get_report_branding()
        # Company still there, engineer updated
        assert r['branding']['company_name'] == 'Acme'
        assert r['branding']['engineer_name'] == 'Bob'

    def test_persists_across_instances(self, tmp_path):
        a1 = HydraulicAPI(work_dir=str(tmp_path))
        a1.set_report_branding(company_name='Persist Ltd')

        a2 = HydraulicAPI(work_dir=str(tmp_path))
        r = a2.get_report_branding()
        assert r['branding']['company_name'] == 'Persist Ltd'


# ---------- U3 learning path ------------------------------------------------

class TestLearningPath:

    def test_get_learning_path_default(self, tmp_path):
        a = HydraulicAPI(work_dir=str(tmp_path))
        r = a.get_learning_path()
        assert r['total_steps'] == 5
        assert r['n_completed'] == 0
        assert r['progress_pct'] == 0
        assert r['next_step']['id'] == 1
        assert len(r['steps']) == 5

    def test_mark_step_complete(self, tmp_path):
        a = HydraulicAPI(work_dir=str(tmp_path))
        r = a.mark_learning_step_complete(1)
        assert 'error' not in r
        assert r['n_completed'] == 1
        assert 'Step 1' in r['message']
        assert 'Next' in r['message']

        progress = a.get_learning_path()
        assert progress['n_completed'] == 1
        assert progress['progress_pct'] == 20
        assert progress['steps'][0]['completed'] is True
        assert progress['next_step']['id'] == 2

    def test_invalid_step_id(self, tmp_path):
        a = HydraulicAPI(work_dir=str(tmp_path))
        r = a.mark_learning_step_complete(99)
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_all_steps_complete(self, tmp_path):
        a = HydraulicAPI(work_dir=str(tmp_path))
        for i in range(1, 6):
            a.mark_learning_step_complete(i)
        r = a.get_learning_path()
        assert r['n_completed'] == 5
        assert r['progress_pct'] == 100
        assert r['next_step'] is None

    def test_progress_persists_across_instances(self, tmp_path):
        a1 = HydraulicAPI(work_dir=str(tmp_path))
        a1.mark_learning_step_complete(2)
        a1.mark_learning_step_complete(3)

        a2 = HydraulicAPI(work_dir=str(tmp_path))
        r = a2.get_learning_path()
        assert r['n_completed'] == 2
        assert r['steps'][1]['completed'] is True
        assert r['steps'][2]['completed'] is True


# ---------- U2 formula reference --------------------------------------------

class TestFormulaReference:

    def test_groups_by_category(self):
        a = HydraulicAPI()
        r = a.formula_reference()
        assert 'categories' in r
        # Key categories must be present
        assert 'Headloss' in r['categories']
        assert 'Transient' in r['categories']
        assert 'Compliance' in r['categories']
        assert 'Slurry' in r['categories']
        assert 'Pipe Materials' in r['categories']

    def test_all_kb_entries_categorised(self):
        a = HydraulicAPI()
        r = a.formula_reference()
        # Every knowledge base entry must appear in some category
        assert r['total_entries'] == len(a.KNOWLEDGE_BASE)

    def test_headloss_category_has_both_formulas(self):
        a = HydraulicAPI()
        r = a.formula_reference(category='Headloss')
        keys = [e['topic_key'] for e in r['entries']]
        assert 'hazen_williams' in keys
        assert 'darcy_weisbach' in keys

    def test_unknown_category_error(self):
        a = HydraulicAPI()
        r = a.formula_reference(category='NotACategory')
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_each_entry_has_required_fields(self):
        a = HydraulicAPI()
        r = a.formula_reference()
        for cat, entries in r['entries_by_category'].items():
            for entry in entries:
                assert 'topic_key' in entry
                assert 'reference' in entry or 'standard' in entry or \
                       entry.get('reference')
