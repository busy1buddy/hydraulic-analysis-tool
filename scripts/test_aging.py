import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epanet_api import HydraulicAPI

def test_aging():
    api = HydraulicAPI()
    api.create_network("aging_test")
    
    api.add_reservoir("R", 100)
    api.add_junction("J", 50)
    
    # Add a Ductile Iron pipe
    api.add_pipe("P1", "R", "J", length=1000, diameter_m=0.3, roughness=140)
    # Set the description as the bulk tool would
    api.update_pipe("P1", description="Material: Ductile Iron, DN: 300")
    
    # Add a PE pipe
    api.add_junction("J_END", 40)
    api.add_pipe("P2", "J", "J_END", length=1000, diameter_m=0.2, roughness=150)
    api.update_pipe("P2", description="Material: PE, DN: 200")
    
    print("Initial C-factors:")
    print(f"  P1 (DI): {api.get_link('P1').roughness}")
    print(f"  P2 (PE): {api.get_link('P2').roughness}")
    
    # Age by 50 years
    res = api.apply_network_aging(50)
    print("\nAging Result:", res['message'])
    
    # DI: 140 - (1.0 * 50) = 90
    # PE: 150 - (0.1 * 50) = 145 (clamped to 140)
    # Wait, PE min is 140.
    
    p1_c = api.get_link("P1").roughness
    p2_c = api.get_link("P2").roughness
    
    print("\nFinal C-factors:")
    print(f"  P1 (DI): {p1_c}")
    print(f"  P2 (PE): {p2_c}")
    
    if p1_c == 90 and p2_c == 145.0:
        print("\nTest PASSED: Aging applied correctly based on material models.")
    else:
        print("\nTest FAILED: C-factors did not match expected values.")

if __name__ == "__main__":
    test_aging()
