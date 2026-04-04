"""
Tests for Design Compliance Certificate (L1)
=============================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestComplianceCertificate:

    @pytest.fixture
    def compliant_api(self):
        """Network designed to pass all checks."""
        api = HydraulicAPI()
        api.create_network(
            name='compliant',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 2, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -200, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 300, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 200,
                 'diameter': 300, 'roughness': 130},
            ],
        )
        return api

    @pytest.fixture
    def failing_api(self):
        """Network with low pressure (high elevation, low head)."""
        api = HydraulicAPI()
        api.create_network(
            name='failing',
            junctions=[
                {'id': 'J1', 'elevation': 45, 'demand': 5, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 48, 'demand': 5, 'x': 200, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 55, 'x': -200, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 500,
                 'diameter': 100, 'roughness': 100},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 500,
                 'diameter': 100, 'roughness': 100},
            ],
        )
        return api

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.run_design_compliance_check()
        assert 'error' in result

    def test_certificate_structure(self, compliant_api):
        cert = compliant_api.run_design_compliance_check()
        assert 'checks' in cert
        assert 'overall_status' in cert
        assert 'summary' in cert
        assert 'date' in cert
        assert 'software_version' in cert
        assert 'network_name' in cert

    def test_certificate_has_all_checks(self, compliant_api):
        """Certificate should include pressure, velocity, fire flow, stress checks."""
        cert = compliant_api.run_design_compliance_check()
        check_names = [c['check'] for c in cert['checks']]
        assert any('Pressure' in n for n in check_names)
        assert any('Velocity' in n for n in check_names)
        assert any('Fire' in n for n in check_names)
        assert any('Stress' in n for n in check_names)

    def test_each_check_has_required_fields(self, compliant_api):
        cert = compliant_api.run_design_compliance_check()
        for check in cert['checks']:
            assert 'check' in check
            assert 'status' in check
            assert check['status'] in ('PASS', 'FAIL', 'ERROR', 'NOT RUN')

    def test_compliant_network_passes(self, compliant_api):
        """A well-designed network should get COMPLIANT status."""
        cert = compliant_api.run_design_compliance_check()
        # At minimum pressure and velocity should pass
        pressure_check = [c for c in cert['checks'] if 'Pressure' in c['check']][0]
        assert pressure_check['status'] == 'PASS'
        velocity_check = [c for c in cert['checks'] if 'Velocity' in c['check']][0]
        assert velocity_check['status'] == 'PASS'

    def test_failing_network_detected(self, failing_api):
        """Network with low pressure should fail."""
        cert = failing_api.run_design_compliance_check()
        # Should detect pressure failures or overall non-compliant
        has_failure = any(c['status'] in ('FAIL', 'ERROR') for c in cert['checks'])
        assert has_failure or cert['overall_status'] != 'COMPLIANT'

    def test_summary_counts_correct(self, compliant_api):
        cert = compliant_api.run_design_compliance_check()
        summary = cert['summary']
        assert summary['total_checks'] == len(cert['checks'])
        assert summary['passed'] + summary['failed'] <= summary['total_checks']

    def test_date_format(self, compliant_api):
        cert = compliant_api.run_design_compliance_check()
        # Date should be a string like "04 April 2026"
        assert isinstance(cert['date'], str)
        assert len(cert['date']) > 5

    def test_software_version_present(self, compliant_api):
        cert = compliant_api.run_design_compliance_check()
        assert cert['software_version'] is not None
        assert len(cert['software_version']) > 0

    def test_standard_references_present(self, compliant_api):
        """Each passing check should reference the relevant standard."""
        cert = compliant_api.run_design_compliance_check()
        for check in cert['checks']:
            if check['status'] == 'PASS':
                assert 'standard' in check, f"Check '{check['check']}' missing standard reference"
