import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

def test_network_validator():
    api = HydraulicAPI()
    api.create_network("test_validator")
    
    # 1. Missing sources
    res1 = api.validate_network()
    print("Test 1 (Empty Network):", res1['errors'])
    
    # 2. Disconnected segment and missing elevation
    api.add_reservoir("R1", 100)
    api.add_junction("J1", elevation=50)
    api.add_pipe("P1", "R1", "J1")
    
    api.add_junction("J2") # Missing elevation (defaults to 0 but let's test if we catch it or if it defaults)
    api.add_junction("J3", elevation=60)
    api.add_pipe("P2", "J2", "J3") # Disconnected from main network
    
    res2 = api.validate_network()
    print("\nTest 2 (Disconnected & Missing Elev):")
    print("Errors:")
    for e in res2['errors']: print(" -", e)
    print("Warnings:")
    for w in res2['warnings']: print(" -", w)
    
    # 3. Valid network
    api.add_pipe("P3", "J1", "J2") # Connect them
    api.update_junction("J2", elevation=55) # Fix elevation
    
    res3 = api.validate_network()
    print("\nTest 3 (Valid Network):", res3['status'])

if __name__ == "__main__":
    test_network_validator()
