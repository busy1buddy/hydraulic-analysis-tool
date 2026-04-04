"""
REST API Mode (L6)
===================
Lightweight HTTP API for remote/programmatic access to HydraulicAPI.
Run: python rest_api.py --port 8080
"""

import os
import sys
import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_api import HydraulicAPI


# Global API instance
_api = HydraulicAPI()


class HydraulicHandler(BaseHTTPRequestHandler):
    """Handle REST requests for hydraulic analysis."""

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode())

    def _error(self, msg, status=400):
        self._json_response({'error': msg}, status)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        params = parse_qs(parsed.query)

        routes = {
            '/health': self._health,
            '/api/summary': self._summary,
            '/api/topology': self._topology,
            '/api/fingerprint': self._fingerprint,
            '/api/diagnose': self._diagnose,
            '/api/compliance': self._compliance,
            '/api/nodes': self._nodes,
            '/api/pipes': self._pipes,
        }

        handler = routes.get(path)
        if handler:
            try:
                handler(params)
            except Exception as e:
                self._error(str(e), 500)
        else:
            self._error(f'Unknown endpoint: {path}', 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._error('Invalid JSON body')
            return

        routes = {
            '/api/load': self._load,
            '/api/steady': self._steady,
            '/api/fire-flow': self._fire_flow,
            '/api/sensitivity': self._sensitivity,
        }

        handler = routes.get(path)
        if handler:
            try:
                handler(data)
            except Exception as e:
                self._error(str(e), 500)
        else:
            self._error(f'Unknown endpoint: {path}', 404)

    # GET handlers

    def _health(self, params):
        self._json_response({
            'status': 'ok',
            'version': _api.SOFTWARE_VERSION,
            'network_loaded': _api.wn is not None,
        })

    def _summary(self, params):
        if _api.wn is None:
            self._error('No network loaded')
            return
        self._json_response(_api.get_network_summary())

    def _topology(self, params):
        result = _api.analyse_topology()
        self._json_response(result)

    def _fingerprint(self, params):
        result = _api.hydraulic_fingerprint()
        self._json_response(result)

    def _diagnose(self, params):
        result = _api.diagnose_network()
        self._json_response(result)

    def _compliance(self, params):
        result = _api.run_design_compliance_check()
        self._json_response(result)

    def _nodes(self, params):
        if _api.wn is None:
            self._error('No network loaded')
            return
        nodes = []
        for jid in _api.wn.junction_name_list:
            j = _api.wn.get_node(jid)
            try:
                demand = j.demand_timeseries_list[0].base_value * 1000
            except (IndexError, AttributeError):
                demand = 0
            nodes.append({
                'id': jid, 'type': 'junction',
                'elevation_m': j.elevation,
                'demand_lps': round(demand, 2),
            })
        for rid in _api.wn.reservoir_name_list:
            r = _api.wn.get_node(rid)
            nodes.append({
                'id': rid, 'type': 'reservoir',
                'head_m': getattr(r, 'base_head', 0),
            })
        self._json_response({'nodes': nodes, 'count': len(nodes)})

    def _pipes(self, params):
        if _api.wn is None:
            self._error('No network loaded')
            return
        pipes = []
        for pid in _api.wn.pipe_name_list:
            p = _api.wn.get_link(pid)
            pipes.append({
                'id': pid,
                'start': p.start_node_name,
                'end': p.end_node_name,
                'length_m': round(p.length, 1),
                'diameter_mm': int(p.diameter * 1000),
                'roughness': p.roughness,
            })
        self._json_response({'pipes': pipes, 'count': len(pipes)})

    # POST handlers

    def _load(self, data):
        path = data.get('path')
        if not path:
            self._error('Missing "path" field')
            return
        if not os.path.exists(path):
            self._error(f'File not found: {path}', 404)
            return
        _api.load_network_from_path(path)
        self._json_response({
            'status': 'loaded',
            'summary': _api.get_network_summary(),
        })

    def _steady(self, data):
        result = _api.run_steady_state(save_plot=False)
        self._json_response(result)

    def _fire_flow(self, data):
        node = data.get('node')
        if not node:
            self._error('Missing "node" field')
            return
        flow = data.get('flow_lps', 25)
        result = _api.run_fire_flow(node, fire_flow_lps=flow, save_plot=False)
        self._json_response(result)

    def _sensitivity(self, data):
        param = data.get('parameter', 'roughness')
        pct = data.get('variation_pct', 10)
        result = _api.sensitivity_analysis(param, variation_pct=pct)
        self._json_response(result)

    def log_message(self, format, *args):
        """Suppress default logging unless verbose."""
        pass


def run_server(port=8080, verbose=False):
    """Start the REST API server."""
    if verbose:
        HydraulicHandler.log_message = BaseHTTPRequestHandler.log_message
    server = HTTPServer(('localhost', port), HydraulicHandler)
    print(f"Hydraulic REST API running on http://localhost:{port}")
    print(f"  GET  /health          — Server status")
    print(f"  POST /api/load        — Load network (body: {{\"path\": \"...\"}})")
    print(f"  POST /api/steady      — Run steady-state analysis")
    print(f"  GET  /api/summary     — Network summary")
    print(f"  GET  /api/topology    — Topology analysis")
    print(f"  GET  /api/fingerprint — Hydraulic fingerprint")
    print(f"  GET  /api/diagnose    — Network diagnostics")
    print(f"  GET  /api/compliance  — Compliance certificate")
    print(f"  GET  /api/nodes       — List all nodes")
    print(f"  GET  /api/pipes       — List all pipes")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Hydraulic Analysis REST API')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    run_server(args.port, args.verbose)
