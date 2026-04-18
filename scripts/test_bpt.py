import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epanet_api import HydraulicAPI

def test_bpt_placement():
    api = HydraulicAPI()
    api.create_network("bpt_test")
    
    # Add a source at 200m elevation
    api.add_reservoir("RES1", 210.0, coordinates=(0, 0))
    
    # Add junctions with a steep drop to 0m over 2km
    # J1: 150m, J2: 100m, J3: 50m, J4: 0m
    api.add_junction("J1", elevation=150.0, coordinates=(500, 0))
    api.add_junction("J2", elevation=100.0, coordinates=(1000, 0))
    api.add_junction("J3", elevation=50.0, coordinates=(1500, 0))
    api.add_junction("J4", elevation=0.0, coordinates=(2000, 0))
    
    api.add_pipe("P1", "RES1", "J1", length=500)
    api.add_pipe("P2", "J1", "J2", length=500)
    api.add_pipe("P3", "J2", "J3", length=500)
    api.add_pipe("P4", "J3", "J4", length=500)
    
    print("Initial summary:", api.get_network_summary())
    
    # Run BPT heuristic with 80m limit
    # RES1 head = 210m.
    # J1 (150m): head - elev = 60m (OK)
    # J2 (100m): head - elev = 110m (VIOLATION > 80m)
    # Heuristic should place BPT at J1 (previous node).
    res = api.auto_place_break_pressure_tanks(max_static_head_m=80.0)
    
    print("\nBPT Result:", res['message'])
    for tank in res.get('details', []):
        print(f"  Placed {tank['id']} at {tank['replaced']} (Elev: {tank['elevation']}m, New Head: {tank['head']}m)")
        
    summary = api.get_network_summary()
    print("\nFinal summary:", summary)
    
    # After BPT at J1, the new head is 155m (150m + 5m level).
    # J2 (100m): 155 - 100 = 55m (OK)
    # J3 (50m): 155 - 50 = 105m (VIOLATION > 80m)
    # Heuristic should place another BPT at J2.
    
    if res['tanks_placed'] >= 2:
        print("\nTest PASSED: Multiple BPTs placed correctly.")
    else:
        print("\nTest FAILED: Expected at least 2 BPTs.")

if __name__ == "__main__":
    test_bpt_placement()
