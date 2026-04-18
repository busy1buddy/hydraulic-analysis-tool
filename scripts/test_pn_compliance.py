import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

def test_pn_compliance():
    api = HydraulicAPI()
    api.create_network("test_pn")

    # Reservoir at 150m, junction at 0m (150m static head)
    api.add_reservoir("R1", 150.0)
    api.add_junction("J1", elevation=0.0)
    api.set_node_demand("J1", 10.0)  # some flow
    
    # Pipe with PN10 rating (max 100m)
    api.add_pipe("P1", "R1", "J1", length=1000, diameter_m=0.3)
    api.update_pipe("P1", description="Material: PE100 PN10 (SDR 17), DN: 315")

    res = api.run_steady_state()
    print("PN10 Pipe Compliance:")
    for comp in res.get('compliance', []):
        if comp['element'] == 'J1' and 'Max pressure' in comp['message']:
            print("  ", comp['message'])

    # Update to PN16 (max 160m)
    api.update_pipe("P1", description="Material: PE100 PN16 (SDR 11), DN: 315")
    res2 = api.run_steady_state()
    print("\nPN16 Pipe Compliance:")
    found_warning = False
    for comp in res2.get('compliance', []):
        if comp['element'] == 'J1' and 'Max pressure' in comp['message']:
            print("  ", comp['message'])
            found_warning = True
    
    if not found_warning:
        print("   No max pressure warning for J1! (As expected, 150m < 160m)")

def test_pn_propagation():
    api = HydraulicAPI()
    api.create_network("test_propagation")
    
    # R1 -> J1 -> J2
    # R1 is at 150m. J1 and J2 are at 0m. (Static head = 150m)
    api.add_reservoir("R1", 150.0)
    api.add_junction("J1", elevation=0.0)
    api.add_junction("J2", elevation=0.0)
    api.set_node_demand("J2", 5.0)
    
    # Pipe 1: PN20 (200m)
    api.add_pipe("P1", "R1", "J1", length=1000)
    api.update_pipe("P1", description="Material: PE100 PN20 (SDR 9), DN: 315")
    
    # Pipe 2: PN10 (100m)
    api.add_pipe("P2", "J1", "J2", length=1000)
    api.update_pipe("P2", description="Material: PE100 PN10 (SDR 17), DN: 315")
    
    res = api.run_steady_state()
    print("\nPropagation Test (PN20 meets PN10 at J1):")
    
    for comp in res.get('compliance', []):
        if 'Max pressure' in comp['message']:
            print(f"  {comp['element']}: {comp['message']}")

if __name__ == "__main__":
    print("--- Test 1: PN Compliance ---")
    test_pn_compliance()
    
    print("\n--- Test 2: PN Propagation ---")
    test_pn_propagation()
