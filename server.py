"""
EPANET Dashboard Server
========================
FastAPI backend serving the hydraulic analysis dashboard.
Wraps epanet_api.py and serves the web frontend.
"""

import os
import sys
import io
import json
import traceback

# Fix Windows encoding before any other imports (skip if pytest or already wrapped)
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.platform == 'win32' and hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

# Import our API
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_api import HydraulicAPI

app = FastAPI(title="EPANET Hydraulic Analysis Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
api = HydraulicAPI(WORK_DIR)


# ── JSON serializer for numpy types ──────────────────────────────────────
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def safe_json(data):
    return JSONResponse(content=json.loads(json.dumps(data, cls=NumpyEncoder)))


# ── Request models ───────────────────────────────────────────────────────
class TransientRequest(BaseModel):
    inp_file: str = "transient_network.inp"
    valve: str = "V1"
    closure_time: float = 0.5
    start_time: float = 2.0
    wave_speed: float = 1000
    sim_duration: float = 20

class JoukowskyRequest(BaseModel):
    wave_speed: float = 1000
    velocity_change: float = 1.0

class NetworkRequest(BaseModel):
    name: str = "custom_network"
    reservoirs: list = []
    junctions: list = []
    tanks: list = []
    pipes: list = []
    valves: list = []
    duration_hrs: int = 24
    pattern: Optional[list] = None

class PumpTripRequest(BaseModel):
    inp_file: str = "pump_station.inp"
    pump_name: str = "PMP1"
    trip_time: float = 2.0
    sim_duration: float = 30
    wave_speed: float = 1000

class PumpStartupRequest(BaseModel):
    inp_file: str = "pump_station.inp"
    pump_name: str = "PMP1"
    ramp_time: float = 10.0
    sim_duration: float = 30
    wave_speed: float = 1000

class ReportRequest(BaseModel):
    inp_file: str = "australian_network.inp"
    format: str = "docx"
    engineer_name: str = ""
    project_name: str = ""
    include_steady: bool = True
    include_transient: bool = False
    transient_valve: str = "V1"
    transient_closure_time: float = 0.5
    transient_inp_file: Optional[str] = None
    include_fire_flow: bool = False
    fire_flow_node: str = "J1"
    fire_flow_lps: float = 25
    include_water_quality: bool = False


# ── Routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(os.path.join(WORK_DIR, "dashboard.html"))


@app.get("/api/networks")
async def list_networks():
    model_dir = os.path.join(WORK_DIR, 'models')
    files = [f for f in os.listdir(model_dir) if f.endswith('.inp')] if os.path.exists(model_dir) else []
    return safe_json({"networks": files})


@app.get("/api/network/{filename}")
async def get_network_info(filename: str):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        summary = api_instance.load_network(filename)
        wn = api_instance.wn

        # Build detailed node/link data for visualization
        nodes = []
        for name in wn.junction_name_list:
            node = wn.get_node(name)
            nodes.append({
                "id": name, "type": "junction",
                "x": node.coordinates[0], "y": node.coordinates[1],
                "elevation": node.elevation,
                "demand_lps": round(node.base_demand * 1000, 2),
            })
        for name in wn.reservoir_name_list:
            node = wn.get_node(name)
            nodes.append({
                "id": name, "type": "reservoir",
                "x": node.coordinates[0], "y": node.coordinates[1],
                "head": node.base_head,
            })
        for name in wn.tank_name_list:
            node = wn.get_node(name)
            nodes.append({
                "id": name, "type": "tank",
                "x": node.coordinates[0], "y": node.coordinates[1],
                "elevation": node.elevation,
            })

        links = []
        for name in wn.pipe_name_list:
            pipe = wn.get_link(name)
            links.append({
                "id": name, "type": "pipe",
                "start": pipe.start_node_name, "end": pipe.end_node_name,
                "length": pipe.length,
                "diameter_mm": round(pipe.diameter * 1000),
                "roughness": pipe.roughness,
            })
        for name in wn.valve_name_list:
            valve = wn.get_link(name)
            links.append({
                "id": name, "type": "valve",
                "start": valve.start_node_name, "end": valve.end_node_name,
                "diameter_mm": round(valve.diameter * 1000),
            })

        return safe_json({"summary": summary, "nodes": nodes, "links": links})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/steady/{filename}")
async def run_steady(filename: str):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        api_instance.load_network(filename)
        results = api_instance.run_steady_state(save_plot=False)

        # Add time-series data for Plotly charts
        wn = api_instance.wn
        sr = api_instance.steady_results
        pressures = sr.node['pressure']
        flows = sr.link['flowrate']

        hours = (pressures.index / 3600).tolist()

        pressure_series = {}
        for j in wn.junction_name_list:
            pressure_series[j] = pressures[j].tolist()

        flow_series = {}
        for p in wn.pipe_name_list:
            flow_series[p] = (flows[p] * 1000).tolist()  # m3/s to LPS

        results['time_hours'] = hours
        results['pressure_series'] = pressure_series
        results['flow_series'] = flow_series

        return safe_json(results)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/transient")
async def run_transient(req: TransientRequest):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        api_instance.load_network(req.inp_file)
        result = api_instance.run_transient(
            valve_name=req.valve,
            closure_time=req.closure_time,
            start_time=req.start_time,
            wave_speed=req.wave_speed,
            sim_duration=req.sim_duration,
            save_plot=False,
        )

        # Add time-series for Plotly
        tm = api_instance.tm
        t = tm.simulation_timestamps
        if isinstance(t, np.ndarray):
            t = t.tolist()
        elif isinstance(t, list):
            t = [float(x) for x in t]

        head_series = {}
        for node_name in tm.junction_name_list:
            node = tm.get_node(node_name)
            h = node.head
            if isinstance(h, np.ndarray):
                h = h.tolist()
            head_series[node_name] = h

        result['time_seconds'] = t
        result['head_series'] = head_series

        return safe_json(result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/joukowsky")
async def calc_joukowsky(req: JoukowskyRequest):
    api_instance = HydraulicAPI(WORK_DIR)
    result = api_instance.joukowsky(req.wave_speed, req.velocity_change)
    return safe_json(result)


@app.get("/api/fireflow/{filename}")
async def run_fire_flow(filename: str, node: str = "J1", flow: float = 25,
                        min_pressure: float = 12):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        api_instance.load_network(filename)
        result = api_instance.run_fire_flow(
            node_id=node,
            flow_lps=flow,
            min_pressure_m=min_pressure,
            save_plot=False,
        )
        return safe_json(result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/waterquality/{filename}")
async def run_water_quality(filename: str, parameter: str = "age",
                            duration: float = 72):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        api_instance.load_network(filename)
        result = api_instance.run_water_quality(
            parameter=parameter,
            duration_hrs=duration,
            save_plot=False,
        )
        return safe_json(result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/pump-trip")
async def run_pump_trip(req: PumpTripRequest):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        api_instance.load_network(req.inp_file)
        result = api_instance.run_pump_trip(
            pump_name=req.pump_name,
            trip_time=req.trip_time,
            sim_duration=req.sim_duration,
            wave_speed=req.wave_speed,
            save_plot=False,
        )

        # Add time-series for Plotly
        tm = api_instance.tm
        t = tm.simulation_timestamps
        if isinstance(t, np.ndarray):
            t = t.tolist()
        elif isinstance(t, list):
            t = [float(x) for x in t]

        head_series = {}
        for node_name in tm.junction_name_list:
            node = tm.get_node(node_name)
            h = node.head
            if isinstance(h, np.ndarray):
                h = h.tolist()
            head_series[node_name] = h

        result['time_seconds'] = t
        result['head_series'] = head_series

        return safe_json(result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/pump-startup")
async def run_pump_startup(req: PumpStartupRequest):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        api_instance.load_network(req.inp_file)
        result = api_instance.run_pump_startup(
            pump_name=req.pump_name,
            ramp_time=req.ramp_time,
            sim_duration=req.sim_duration,
            wave_speed=req.wave_speed,
            save_plot=False,
        )

        # Add time-series for Plotly
        tm = api_instance.tm
        t = tm.simulation_timestamps
        if isinstance(t, np.ndarray):
            t = t.tolist()
        elif isinstance(t, list):
            t = [float(x) for x in t]

        head_series = {}
        for node_name in tm.junction_name_list:
            node = tm.get_node(node_name)
            h = node.head
            if isinstance(h, np.ndarray):
                h = h.tolist()
            head_series[node_name] = h

        result['time_seconds'] = t
        result['head_series'] = head_series

        return safe_json(result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/report")
async def generate_report(req: ReportRequest):
    try:
        api_instance = HydraulicAPI(WORK_DIR)
        api_instance.load_network(req.inp_file)

        steady_results = None
        transient_results = None
        fire_flow_results = None
        water_quality_results = None

        if req.include_steady:
            steady_results = api_instance.run_steady_state(save_plot=False)

        if req.include_transient:
            t_inp = req.transient_inp_file or req.inp_file
            t_api = HydraulicAPI(WORK_DIR)
            t_api.load_network(t_inp)
            transient_results = t_api.run_transient(
                valve_name=req.transient_valve,
                closure_time=req.transient_closure_time,
                save_plot=False,
            )

        if req.include_fire_flow:
            fire_flow_results = api_instance.run_fire_flow(
                node_id=req.fire_flow_node,
                flow_lps=req.fire_flow_lps,
                save_plot=False,
            )

        if req.include_water_quality:
            water_quality_results = api_instance.run_water_quality(save_plot=False)

        report_path = api_instance.generate_report(
            format=req.format,
            steady_results=steady_results,
            transient_results=transient_results,
            fire_flow_results=fire_flow_results,
            water_quality_results=water_quality_results,
            engineer_name=req.engineer_name,
            project_name=req.project_name,
        )

        if isinstance(report_path, dict) and 'error' in report_path:
            raise HTTPException(status_code=400, detail=report_path['error'])

        return FileResponse(
            path=report_path,
            filename=os.path.basename(report_path),
            media_type='application/octet-stream',
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    print(f"Starting EPANET Dashboard at http://localhost:8765")
    print(f"Working directory: {WORK_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="warning")
