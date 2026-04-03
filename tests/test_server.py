"""Tests for FastAPI server endpoints."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from server import app
    return TestClient(app)


class TestRootEndpoint:
    def test_returns_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "EPANET" in response.text


class TestNetworksEndpoint:
    def test_lists_networks(self, client):
        response = client.get("/api/networks")
        assert response.status_code == 200
        data = response.json()
        assert "networks" in data
        assert isinstance(data["networks"], list)
        assert len(data["networks"]) >= 2

    def test_contains_australian_network(self, client):
        response = client.get("/api/networks")
        data = response.json()
        assert "australian_network.inp" in data["networks"]


class TestNetworkInfoEndpoint:
    def test_returns_summary(self, client):
        response = client.get("/api/network/australian_network.inp")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "nodes" in data
        assert "links" in data
        assert data["summary"]["junctions"] == 7

    def test_invalid_network(self, client):
        response = client.get("/api/network/nonexistent.inp")
        assert response.status_code == 400


class TestSteadyEndpoint:
    def test_returns_results(self, client):
        response = client.get("/api/steady/australian_network.inp")
        assert response.status_code == 200
        data = response.json()
        assert "pressures" in data
        assert "flows" in data
        assert "compliance" in data
        assert "time_hours" in data
        assert "pressure_series" in data


class TestTransientEndpoint:
    def test_returns_results(self, client):
        response = client.post("/api/transient", json={
            "inp_file": "transient_network.inp",
            "valve": "V1",
            "closure_time": 0.5,
            "start_time": 2.0,
            "wave_speed": 1000,
            "sim_duration": 20,
        })
        assert response.status_code == 200
        data = response.json()
        assert "junctions" in data
        assert "max_surge_m" in data

    def test_invalid_valve(self, client):
        response = client.post("/api/transient", json={
            "inp_file": "australian_network.inp",
            "valve": "NONEXISTENT",
        })
        assert response.status_code == 400


class TestJoukowskyEndpoint:
    def test_returns_calculation(self, client):
        response = client.post("/api/joukowsky", json={
            "wave_speed": 1000,
            "velocity_change": 1.5,
        })
        assert response.status_code == 200
        data = response.json()
        assert "head_rise_m" in data
        assert data["head_rise_m"] > 0
