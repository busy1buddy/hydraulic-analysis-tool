import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epanet_api import HydraulicAPI

def test_booster_placement():
    api = HydraulicAPI()
    api.create_network("booster_test")
    
    # Source at 0m
    api.add_reservoir("RES1", 10.0, coordinates=(0, 0))
    
    # Uphill junctions: J1(50m), J2(100m) over 2km
    api.add_junction("J1", elevation=50.0, coordinates=(1000, 0))
    api.add_junction("J2", elevation=100.0, coordinates=(2000, 0))
    
    api.add_pipe("P1", "RES1", "J1", length=1000, diameter_m=0.3)
    api.add_pipe("P2", "J1", "J2", length=1000, diameter_m=0.3)
    
    # Add demand at J2 so there's friction
    api.set_node_demand("J2", 50.0)
    
    print("Initial summary:", api.get_network_summary())
    
    # Run booster heuristic
    # Initially, J1 (50m) and J2 (100m) will have negative pressure (head 10m).
    res = api.auto_place_booster_pumps(min_pressure_m=20.0, target_boost_kw=100.0)
    print("Result Dict:", res)
    
    if 'message' in res:
        print("\nBooster Result:", res['message'])
    for pump in res.get('details', []):
        print(f"  Placed {pump['id']} (Replacing {pump['replaced_pipe']}) from {pump['from']} to {pump['to']}")
        
    summary = api.get_network_summary()
    print("\nFinal summary:", summary)
    
    if summary['pumps'] >= 1:
        print("\nTest PASSED: Booster pump placed correctly.")
    else:
        print("\nTest FAILED: No pump placed.")

if __name__ == "__main__":
    test_booster_placement()
