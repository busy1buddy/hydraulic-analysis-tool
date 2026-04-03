"""Tests for HydraulicAPI core methods: load, create, list, joukowsky, export."""

import os
import json
import pytest


class TestInit:
    def test_creates_directories(self, tmp_path):
        from epanet_api import HydraulicAPI
        api = HydraulicAPI(work_dir=str(tmp_path))
        assert os.path.isdir(api.model_dir)
        assert os.path.isdir(api.output_dir)

    def test_defaults_set(self, api_instance):
        assert api_instance.DEFAULTS['flow_units'] == 'LPS'
        assert api_instance.DEFAULTS['min_pressure_m'] == 20
        assert api_instance.DEFAULTS['pipe_rating_kPa'] == 3500


class TestLoadNetwork:
    def test_returns_summary(self, api_instance):
        summary = api_instance.load_network('australian_network.inp')
        assert summary['junctions'] == 7
        assert summary['reservoirs'] == 1
        assert summary['tanks'] == 1
        assert summary['pipes'] == 9

    def test_sets_wn_object(self, loaded_network):
        assert loaded_network.wn is not None

    def test_lists_junctions(self, loaded_network):
        summary = loaded_network.get_network_summary()
        assert 'J1' in summary['junction_list']
        assert 'J7' in summary['junction_list']

    def test_file_not_found(self, api_instance):
        with pytest.raises(Exception):
            api_instance.load_network('nonexistent_file.inp')


class TestCreateNetwork:
    def test_saves_inp_file(self, api_instance, simple_network_params):
        api_instance.create_network(**simple_network_params)
        inp_path = os.path.join(api_instance.model_dir, 'test_simple.inp')
        assert os.path.exists(inp_path)

    def test_roundtrip(self, api_instance, simple_network_params):
        api_instance.create_network(**simple_network_params)
        summary = api_instance.load_network('test_simple.inp')
        assert summary['junctions'] == 2
        assert summary['reservoirs'] == 1
        assert summary['pipes'] == 2


class TestListNetworks:
    def test_lists_inp_files(self, api_instance):
        networks = api_instance.list_networks()
        assert 'australian_network.inp' in networks
        assert 'transient_network.inp' in networks

    def test_count(self, api_instance):
        networks = api_instance.list_networks()
        assert len(networks) >= 2


class TestJoukowsky:
    def test_basic_calculation(self, api_instance):
        result = api_instance.joukowsky(wave_speed=1000, velocity_change=1.0)
        assert abs(result['head_rise_m'] - 101.9) < 1.0
        assert abs(result['pressure_rise_kPa'] - 1000.0) < 10.0

    def test_zero_velocity(self, api_instance):
        result = api_instance.joukowsky(wave_speed=1000, velocity_change=0)
        assert result['head_rise_m'] == 0
        assert result['pressure_rise_kPa'] == 0

    def test_returns_inputs(self, api_instance):
        result = api_instance.joukowsky(wave_speed=400, velocity_change=2.0)
        assert result['wave_speed_ms'] == 400
        assert result['velocity_change_ms'] == 2.0


class TestExportJSON:
    def test_exports_file(self, api_instance, steady_results):
        path = api_instance.export_results_json(steady_results, 'test_export.json')
        assert os.path.exists(path)

    def test_valid_json(self, api_instance, steady_results):
        path = api_instance.export_results_json(steady_results, 'test_export.json')
        with open(path) as f:
            data = json.load(f)
        assert 'pressures' in data
