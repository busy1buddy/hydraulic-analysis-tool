import os
import sys
import unittest
import wntr

# Add current directory to path to find epanet_api and importers
sys.path.append(os.getcwd())

from epanet_api import HydraulicAPI
from data.fluid_properties import get_fluid

class Phase1IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.api = HydraulicAPI()
        
    def test_end_to_end_pipeline(self):
        print("\n--- Starting Phase 1 End-to-End Integration Test ---")
        
        # 1. Simulate DXF Geometry Import (Sessions 1-3)
        # We manually build the network that would result from a DXF import
        print("1. Simulating DXF Geometry Import...")
        self.api.create_network("test_pipeline")
        
        # Add a series of junctions representing a 10km pipeline
        # J0 is Point A (Intake), J10 is Point B (Delivery)
        for i in range(11):
            # Elevation decreases from 100m to 80m
            self.api.add_junction(f"J{i}", elevation=100-i*2, coordinates=(i*1000, 0))
            
        # Add pipes (DN300, PN16 equivalent)
        for i in range(10):
            self.api.add_pipe(f"P{i}", f"J{i}", f"J{i+1}", length=1000, diameter_m=0.3)
            
        print(f"   Nodes: {len(self.api.wn.node_name_list)}, Pipes: {len(self.api.wn.pipe_name_list)}")
        self.assertEqual(len(self.api.wn.junction_name_list), 11)
        self.assertEqual(len(self.api.wn.pipe_name_list), 10)

        # 2. Fluid Properties (Session 6)
        print("2. Setting Fluid Properties (Slurry)...")
        fluid = get_fluid("mine_tailings_30pct")
        self.assertIsNotNone(fluid, "Fluid 'mine_tailings_30pct' not found in catalogue")
        print(f"   Fluid: {fluid.name}, Density: {fluid.density_kg_m3} kg/m3")
        self.assertEqual(fluid.joukowsky_density(), 1300.0)

        # 3. Auto-Generate Source Reservoir (Session 7)
        print("3. Auto-generating Source Reservoir (Point A)...")
        # Strategy 'highest_elevation' should pick J0 (elev 100m)
        res_info = self.api.auto_generate_source_reservoir(
            reservoir_id='RES_SOURCE',
            strategy='highest_elevation',
            freeboard_m=5.0
        )
        self.assertEqual(res_info['status'], 'success')
        self.assertEqual(res_info['reservoir_id'], 'RES_SOURCE')
        self.assertEqual(res_info['replaced_junction'], 'J0')
        self.assertEqual(res_info['head_m'], 105.0) # 100 + 5
        print(f"   Source set at {res_info['replaced_junction']} with head {res_info['head_m']}m")

        # 4. Auto-Generate Delivery Tank (Session 8)
        print("4. Auto-generating Delivery Tank (Point B)...")
        # Strategy 'lowest_elevation' should pick J10 (elev 80m)
        tank_info = self.api.auto_generate_delivery_tank(
            tank_id='TANK_DELIVERY',
            strategy='lowest_elevation',
            diameter_m=20.0,
            max_level_m=6.0
        )
        self.assertEqual(tank_info['status'], 'success')
        self.assertEqual(tank_info['tank_id'], 'TANK_DELIVERY')
        self.assertEqual(tank_info['replaced_junction'], 'J10')
        self.assertEqual(tank_info['elevation_m'], 80.0)
        print(f"   Delivery tank set at {tank_info['replaced_junction']} (Elev: {tank_info['elevation_m']}m, Vol: {tank_info['volume_m3']}m3)")

        # 5. Wire up Demands (Session 9)
        print("5. Wiring up Destination Demands...")
        # Assign 50 LPS demand to J9 (just before the tank)
        demand_info = self.api.set_node_demand('J9', 50.0)
        self.assertEqual(demand_info['status'], 'success')
        self.assertEqual(self.api.get_node_demand('J9')['demand_lps'], 50.0)
        print(f"   Demand of 50 LPS assigned to node J9")

        # 6. Verify Hydraulic Solve (Final Gate)
        print("6. Verifying Steady-State Solve...")
        # With Head at 105m and Tank at 80m+3m level, gravity flow will occur.
        results = self.api.run_steady_state(save_plot=False)
        self.assertNotIn('error', results)
        
        # Verify flow is occurring in the first pipe
        p0_results = results['flows']['P0']
        flow_lps = p0_results['avg_lps']
        velocity = p0_results['avg_velocity_ms']
        
        print(f"   P0 Flow: {flow_lps:.2f} LPS")
        print(f"   P0 Velocity: {velocity:.2f} m/s")
        
        self.assertGreater(flow_lps, 0, "Gravity flow should be positive")
        self.assertGreater(velocity, 0, "Velocity should be positive")
        
        # Check compliance messages
        print("   Compliance Check:")
        for issue in results['compliance']:
            print(f"     [{issue['type']}] {issue['element']}: {issue['message']}")

        print("\n--- Phase 1 Integration Test: SUCCESS ---")

if __name__ == '__main__':
    unittest.main()
