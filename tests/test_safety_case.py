"""
Safety Case Report Tests (Innovation #2)
=========================================
Regulatory-grade safety case: pressure, surge, water hammer, slurry settling.
Formal output with explicit PASS/FAIL margins for each check.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


def _simple_api():
    a = HydraulicAPI()
    a.create_network(
        name='safety_case_test',
        junctions=[
            {'id': 'J1', 'elevation': 10, 'demand': 5, 'x': 0, 'y': 0},
            {'id': 'J2', 'elevation': 15, 'demand': 3, 'x': 500, 'y': 0},
        ],
        reservoirs=[{'id': 'R1', 'head': 60, 'x': -100, 'y': 0}],
        pipes=[
            {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
             'diameter': 200, 'roughness': 130},
            {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 500,
             'diameter': 150, 'roughness': 130},
        ],
    )
    return a


class TestSafetyCaseReport:

    def test_no_network_error(self):
        a = HydraulicAPI()
        r = a.safety_case_report()
        assert 'error' in r
        assert 'Fix:' in r['error']

    def test_generates_report(self):
        a = _simple_api()
        r = a.safety_case_report()
        assert 'error' not in r
        assert r['title'] == 'Pipeline Safety Case Report'
        assert 'sections' in r
        assert 'overall_verdict' in r
        assert len(r['sections']) >= 3

    def test_sections_cover_required_areas(self):
        a = _simple_api()
        r = a.safety_case_report()
        titles = ' '.join(s['section'] for s in r['sections'])
        assert 'Steady-State' in titles
        assert 'Transient' in titles or 'Joukowsky' in titles
        assert 'Water Hammer' in titles

    def test_every_check_has_standard(self):
        a = _simple_api()
        r = a.safety_case_report()
        for section in r['sections']:
            assert 'standard' in section

    def test_checks_include_margins(self):
        a = _simple_api()
        r = a.safety_case_report()
        for section in r['sections']:
            if section['section'].startswith('1.'):
                for check in section['checks']:
                    assert 'margin' in check
                    assert '+' in check['margin'] or '-' in check['margin']

    def test_slurry_section_optional(self):
        a = _simple_api()
        r_no_slurry = a.safety_case_report()
        r_slurry = a.safety_case_report(slurry_critical_velocity_ms=1.5)
        assert len(r_slurry['sections']) > len(r_no_slurry['sections'])
        slurry_section = [s for s in r_slurry['sections']
                          if 'Slurry' in s['section']]
        assert len(slurry_section) == 1

    def test_verdict_categories(self):
        a = _simple_api()
        r = a.safety_case_report()
        assert r['overall_verdict'] in (
            'APPROVED', 'CONDITIONAL APPROVAL', 'NOT APPROVED')

    def test_signature_block_present(self):
        a = _simple_api()
        r = a.safety_case_report()
        assert 'signature_block' in r
        assert 'disclaimer' in r['signature_block']
        assert 'RPEQ' in r['signature_block']['disclaimer'] or \
               'engineer' in r['signature_block']['disclaimer'].lower()

    def test_low_pn_rating_triggers_surge_fail(self):
        a = _simple_api()
        # Deliberately low PN rating → surge margin negative
        r = a.safety_case_report(max_transient_pressure_m=20.0)
        surge_section = next(
            s for s in r['sections'] if 'Transient' in s['section'])
        assert surge_section['overall'] == 'FAIL'
        assert r['overall_verdict'] == 'NOT APPROVED'

    def test_assumptions_documented(self):
        """Report must explicitly document modelling assumptions for regulator."""
        a = _simple_api()
        r = a.safety_case_report()
        assert 'assumptions' in r
        assert len(r['assumptions']) >= 3
        topics = ' '.join(str(a.get('item', '')) for a in r['assumptions'])
        assert 'Joukowsky' in topics
        assert 'Critical period' in topics or 'critical' in topics.lower()
        # Rigid-pipe assumption must be called out
        all_text = str(r['assumptions']).lower()
        assert 'rigid' in all_text or 'conservative' in all_text

    def test_audit_trail_fields_present(self):
        a = _simple_api()
        r = a.safety_case_report()
        # ISO8601 UTC timestamp
        assert 'issued_utc_iso8601' in r
        assert 'T' in r['issued_utc_iso8601']
        # Network hash field (may be None if network was created in-memory)
        assert 'network_sha256' in r
        # Signature flag
        assert r['signature_block']['is_digitally_signed'] is False
        # Disclaimer names the limitation
        disc = r['signature_block']['disclaimer'].lower()
        assert 'cryptographic' in disc or 'visual only' in disc

    def test_network_hash_populated_for_loaded_file(self, tmp_path):
        """When loaded from an .inp file, network_sha256 must be populated."""
        a = _simple_api()
        inp_path = str(tmp_path / 'net.inp')
        a.write_inp(inp_path)
        a.load_network(inp_path)
        r = a.safety_case_report()
        assert r['network_sha256'] is not None
        assert len(r['network_sha256']) == 64  # SHA-256 hex length

    def test_fast_closure_triggers_review(self):
        a = _simple_api()
        # 0.01s closure on 500m pipe with a=1100 → critical period ~0.9s
        r = a.safety_case_report(valve_closure_s=0.01, wave_speed_ms=1100)
        wh_section = next(
            s for s in r['sections'] if 'Water Hammer' in s['section'])
        assert wh_section['overall'] == 'REVIEW'
