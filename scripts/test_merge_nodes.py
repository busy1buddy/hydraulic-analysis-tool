import sys
import os
import wntr
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

def test_merge_api():
    api = HydraulicAPI()
    api.create_network("test_merge")
    api.add_junction("J1", coordinates=(0,0))
    api.add_junction("J2", coordinates=(10,0), base_demand=5.0)
    api.add_junction("J3", coordinates=(10.01,0), base_demand=2.0)
    
    api.add_pipe("P1", "J1", "J2", length=100)
    api.add_pipe("P2", "J3", "J1", length=100)
    api.add_pipe("P3", "J2", "J3", length=1) # small loop
    
    # Merge J3 into J2
    res = api.merge_nodes("J3", "J2")
    print("Merge result:", res)
    
    wn = api.wn
    print("Nodes:", wn.node_name_list)
    print("Links:", wn.link_name_list)
    
    # check new P2 properties
    p2 = wn.get_link("P2")
    print("P2 start:", p2.start_node_name, "end:", p2.end_node_name, "length:", p2.length)
    
    # check demand of J2
    j2 = wn.get_node("J2")
    print("J2 demand:", j2.demand_timeseries_list[0].base_value)

if __name__ == "__main__":
    test_merge_api()
