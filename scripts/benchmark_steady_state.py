import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI

def benchmark_steady_state(num_nodes=1000):
    api = HydraulicAPI()
    api.create_network("benchmark")
    
    # Create a linear network of `num_nodes` junctions
    api.add_reservoir("R1", head_m=200.0)
    api.add_junction("J0", elevation=150.0)
    api.add_pipe("P0", "R1", "J0", length=100)
    
    for i in range(1, num_nodes):
        prev_node = f"J{i-1}"
        curr_node = f"J{i}"
        pipe_id = f"P{i}"
        
        # Slight drop in elevation
        api.add_junction(curr_node, elevation=max(0, 150.0 - i * 0.1))
        api.set_node_demand(curr_node, 0.5) # 0.5 LPS demand at each node
        
        api.add_pipe(pipe_id, prev_node, curr_node, length=100, diameter_m=0.3, roughness=130)
        
    print(f"Built network with {num_nodes} nodes and pipes.")
    
    # Warmup run
    print("Running warmup...")
    api.run_steady_state()
    
    # Benchmark runs
    num_runs = 5
    total_time = 0.0
    solver_time = 0.0
    
    print(f"Running benchmark ({num_runs} iterations)...")
    for _ in range(num_runs):
        start_time = time.perf_counter()
        
        res = api.run_steady_state()
        end_time = time.perf_counter()
        
        assert 'error' not in res
        total_time += (end_time - start_time)
        solver_time += res['timing']['solver']
        
    avg_time_ms = (total_time / num_runs) * 1000
    avg_solver_ms = (solver_time / num_runs) * 1000
    
    print(f"\n--- Benchmark Results ---")
    print(f"Network size : {num_nodes} junctions")
    print(f"Average total time : {avg_time_ms:.2f} ms")
    print(f"Average solver time: {avg_solver_ms:.2f} ms")
    print(f"Post-processing    : {(avg_time_ms - avg_solver_ms):.2f} ms")
    
    if avg_time_ms < 250:
        print("Verdict      : FAST ENOUGH for live debounced UI.")
    else:
        print("Verdict      : TOO SLOW. Requires optimization or longer debounce.")

if __name__ == "__main__":
    benchmark_steady_state(1000)
