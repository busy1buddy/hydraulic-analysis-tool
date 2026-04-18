"""
Tests for REST API Mode (L6)
==============================
"""

import os
import sys
import json
import threading
import time
import pytest
from urllib.request import urlopen, Request
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestRestAPI:

    @pytest.fixture(autouse=True)
    def server(self):
        """Start REST API server on random port for testing."""
        from app.rest_api import HydraulicHandler, _api
        from http.server import HTTPServer

        # Load a network for testing
        _api.load_network('australian_network.inp')

        self.httpd = HTTPServer(('localhost', 0), HydraulicHandler)
        self.port = self.httpd.server_address[1]
        self.base = f'http://localhost:{self.port}'

        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()

        yield

        self.httpd.shutdown()

    def _get(self, path):
        resp = urlopen(f'{self.base}{path}')
        return json.loads(resp.read())

    def _post(self, path, data=None):
        body = json.dumps(data or {}).encode()
        req = Request(f'{self.base}{path}', data=body,
                      headers={'Content-Type': 'application/json'})
        resp = urlopen(req)
        return json.loads(resp.read())

    def test_health(self):
        result = self._get('/health')
        assert result['status'] == 'ok'
        assert result['network_loaded'] is True

    def test_summary(self):
        result = self._get('/api/summary')
        assert result['junctions'] > 0
        assert result['pipes'] > 0

    def test_nodes(self):
        result = self._get('/api/nodes')
        assert result['count'] > 0
        assert 'nodes' in result

    def test_pipes(self):
        result = self._get('/api/pipes')
        assert result['count'] > 0
        assert result['pipes'][0]['diameter_mm'] > 0

    def test_topology(self):
        result = self._get('/api/topology')
        assert 'dead_ends' in result
        assert 'loops' in result

    def test_diagnose(self):
        result = self._get('/api/diagnose')
        assert 'issues' in result

    def test_steady_state(self):
        result = self._post('/api/steady')
        assert 'pressures' in result
        assert 'flows' in result

    def test_unknown_endpoint(self):
        with pytest.raises(HTTPError) as exc_info:
            self._get('/api/nonexistent')
        assert exc_info.value.code == 404

    def test_fingerprint(self):
        result = self._get('/api/fingerprint')
        assert 'pressure_stats' in result

    def test_compliance(self):
        result = self._get('/api/compliance')
        assert 'checks' in result
        assert 'overall_status' in result
