import sys
import os
import wntr
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

def test_merge():
    api = HydraulicAPI()
    api.create_network("test_merge")
    api.add_junction("J1", coordinates=(0,0))
    api.add_junction("J2", coordinates=(10,0))
    api.add_junction("J3", coordinates=(10.01,0))
    api.add_pipe("P1", "J1", "J2")
    api.add_pipe("P2", "J3", "J1")
    
    wn = api.wn
    print("Links for J3:", wn.get_links_for_node("J3"))
    
    # Try to change end_node
    pipe = wn.get_link("P2")
    try:
        pipe.start_node_name = "J2"
        print("Success setting start_node_name")
    except Exception as e:
        print("Error setting start_node_name:", e)
        
if __name__ == "__main__":
    test_merge()
