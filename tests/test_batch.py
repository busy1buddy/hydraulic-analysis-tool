"""
Tests for Batch Analysis Mode (L10)
=====================================
"""

import os
import sys
import glob
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, 'models')


class TestBatchAnalysis:

    def test_single_file(self):
        api = HydraulicAPI()
        files = [os.path.join(MODELS, 'australian_network.inp')]
        results = api.batch_analyse(files, analyses=['topology'])
        assert len(results) == 1
        assert 'topology' in results[0]['analyses']

    def test_multiple_files(self):
        api = HydraulicAPI()
        inp_files = glob.glob(os.path.join(MODELS, '*.inp'))[:3]
        if len(inp_files) < 2:
            pytest.skip("Need at least 2 .inp files")
        results = api.batch_analyse(inp_files, analyses=['topology', 'diagnose'])
        assert len(results) == len(inp_files)
        for r in results:
            assert 'file' in r
            if 'error' not in r:
                assert 'topology' in r['analyses']
                assert 'diagnose' in r['analyses']

    def test_nonexistent_file_handled(self):
        api = HydraulicAPI()
        results = api.batch_analyse(['/nonexistent/file.inp'], analyses=['topology'])
        assert len(results) == 1
        assert 'error' in results[0]

    def test_selective_analyses(self):
        api = HydraulicAPI()
        files = [os.path.join(MODELS, 'australian_network.inp')]
        results = api.batch_analyse(files, analyses=['topology'])
        r = results[0]
        assert 'topology' in r['analyses']
        assert 'steady' not in r['analyses']

    def test_all_default_analyses(self):
        api = HydraulicAPI()
        files = [os.path.join(MODELS, 'australian_network.inp')]
        results = api.batch_analyse(files)
        r = results[0]
        assert 'steady' in r['analyses']
        assert 'topology' in r['analyses']
        assert 'fingerprint' in r['analyses']
        assert 'diagnose' in r['analyses']
        assert 'compliance' in r['analyses']

    def test_result_structure(self):
        api = HydraulicAPI()
        files = [os.path.join(MODELS, 'australian_network.inp')]
        results = api.batch_analyse(files, analyses=['topology'])
        r = results[0]
        assert 'file' in r
        assert 'path' in r
        assert 'analyses' in r
