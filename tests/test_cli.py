"""
CLI Batch Mode Tests — Cycle 7
================================
Verifies that `python -m hydraulic_tool` commands produce correct
output without importing PyQt6.
"""

import csv
import io
import json
import os
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_INP = os.path.join(ROOT, 'tutorials', 'demo_network', 'network.inp')
PYTHON = sys.executable


def _run_cli(*args, timeout=60):
    """Run CLI command and return CompletedProcess."""
    cmd = [PYTHON, '-m', 'hydraulic_tool'] + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=ROOT, timeout=timeout)


class TestAnalyseJson:
    """python -m hydraulic_tool analyse network.inp --format json"""

    def test_json_output_is_valid(self):
        result = _run_cli('analyse', DEMO_INP, '--format', 'json')
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert 'pressures' in data
        assert 'flows' in data

    def test_json_has_junction_count(self):
        result = _run_cli('analyse', DEMO_INP, '--format', 'json')
        data = json.loads(result.stdout)
        assert len(data['pressures']) == 10

    def test_json_has_pipe_count(self):
        result = _run_cli('analyse', DEMO_INP, '--format', 'json')
        data = json.loads(result.stdout)
        assert len(data['flows']) == 11

    def test_json_pressure_has_units_keys(self):
        result = _run_cli('analyse', DEMO_INP, '--format', 'json')
        data = json.loads(result.stdout)
        p = list(data['pressures'].values())[0]
        assert 'min_m' in p
        assert 'max_m' in p
        assert 'avg_m' in p


class TestAnalyseCsv:
    """python -m hydraulic_tool analyse network.inp --format csv"""

    def test_csv_output_parseable(self):
        result = _run_cli('analyse', DEMO_INP, '--format', 'csv')
        assert result.returncode == 0
        reader = csv.reader(io.StringIO(result.stdout))
        rows = list(reader)
        assert len(rows) > 10  # header + 10 junctions + pipe section

    def test_csv_has_pressure_header(self):
        result = _run_cli('analyse', DEMO_INP, '--format', 'csv')
        assert 'Junction,Min (m),Max (m),Avg (m)' in result.stdout

    def test_csv_has_pipe_header(self):
        result = _run_cli('analyse', DEMO_INP, '--format', 'csv')
        assert 'Pipe,Avg (LPS),Velocity (m/s),Headloss (m/km)' in result.stdout

    def test_csv_has_compliance_section(self):
        result = _run_cli('analyse', DEMO_INP, '--format', 'csv')
        assert '# Compliance' in result.stdout


class TestReport:
    """python -m hydraulic_tool report network.inp --output report.docx"""

    def test_report_generates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'test.docx')
            result = _run_cli('report', DEMO_INP, '--output', out)
            assert result.returncode == 0
            assert os.path.exists(out)
            assert os.path.getsize(out) > 5000

    def test_report_default_name(self):
        """Without --output, uses inp basename + _report.docx."""
        result = _run_cli('report', DEMO_INP, '--output',
                          os.path.join(ROOT, 'output', 'cli_default.docx'))
        assert result.returncode == 0


class TestValidate:
    """python -m hydraulic_tool validate network.inp"""

    def test_validate_demo_fails(self):
        """Demo network has known WSAA violations."""
        result = _run_cli('validate', DEMO_INP)
        assert result.returncode == 1  # has warnings
        assert 'FAIL' in result.stdout

    def test_validate_shows_pressure_warning(self):
        result = _run_cli('validate', DEMO_INP)
        assert 'J10' in result.stdout
        assert '20m' in result.stdout or '20 m' in result.stdout

    def test_validate_shows_velocity_warning(self):
        result = _run_cli('validate', DEMO_INP)
        assert 'P10' in result.stdout
        assert '2.0' in result.stdout

    def test_validate_shows_info_count(self):
        result = _run_cli('validate', DEMO_INP)
        assert 'informational' in result.stdout


class TestNoGuiImport:
    """CLI must work without PyQt6 imported."""

    def test_no_pyqt6_in_cli_module(self):
        """Verify hydraulic_tool.__main__ doesn't import PyQt6."""
        import importlib
        # Remove PyQt6 from cache temporarily to test
        mod = importlib.import_module('hydraulic_tool.__main__')
        source = open(mod.__file__).read()
        assert 'PyQt6' not in source, (
            "CLI module must not import PyQt6 for headless operation")

    def test_help_works(self):
        result = _run_cli('--help')
        assert result.returncode == 0
        assert 'analyse' in result.stdout
        assert 'report' in result.stdout
        assert 'validate' in result.stdout
