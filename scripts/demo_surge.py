"""
Demo Surge Analysis — Progress & Results
========================================
Runs a 20-second transient simulation on the demo network.
Simulates a valve closure at T=2s.
"""

import os
import sys
import numpy as np

# Add project root to path
sys.path.append(os.getcwd())

from epanet_api import HydraulicAPI

def run_demo_surge():
    api = HydraulicAPI()
    
    # 1. Create a Transient-Ready Network
    print("--- [Progress 1/4] Creating Test Network (Reservoir -> Pipe -> Valve -> Junction) ---")
    api.create_network()
    api.add_reservoir('R1', head_m=100, coordinates=(0, 100))
    api.add_junction('J1', elevation=50, coordinates=(500, 100))
    api.add_junction('J2', elevation=50, coordinates=(1000, 100))
    api.set_node_demand('J2', 10.0)
    api.add_pipe('P1', 'R1', 'J1', length=500, diameter_m=0.3)
    api.add_valve('V1', 'J1', 'J2', diameter_m=0.3, valve_type='TCV', setting=1.0)
    
    # Save it so TSNet can read it
    temp_inp = 'temp_surge.inp'
    api.write_inp(temp_inp)
    api._inp_file = temp_inp # Ensure API knows where the file is
    
    # 2. Configure Transient Event
    valve_id = 'V1'
    print(f"--- [Progress 2/4] Configuring Transient: Valve {valve_id} closure in 0.5s ---")
    
    # 3. Run MOC Simulation
    print(f"--- [Progress 3/4] Running MOC Solver (Water Hammer)... ---")
    results = api.run_transient(valve_id, closure_time=0.5, sim_duration=10.0, save_plot=False)
    
    # 4. Show Results
    print(f"--- [Progress 4/4] Analysis Complete ---")
    if 'error' in results:
        print(f"Error: {results['error']}")
        return

    print("\n==========================================")
    print("      PRESSURE SURGE RESULTS (PEAK)      ")
    print("==========================================")
    print(f"Max Surge Head:    {results['max_surge_m']:.2f} m")
    print(f"Max Surge Pressure: {results['max_surge_kPa']:.1f} kPa")
    print(f"Wave Speed:        {results['wave_speed_ms']:.0f} m/s")
    print("------------------------------------------")
    
    # Recommendations based on AS/NZS 2566
    design = api.design_surge_protection(results)
    print("\n--- Engineering Recommendations ---")
    for msg in design['summary']:
        print(f" - {msg}")
    
    print("\n==========================================")

if __name__ == "__main__":
    run_demo_surge()
