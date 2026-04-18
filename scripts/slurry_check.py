from epanet_api import HydraulicAPI
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api.slurry_solver import bingham_plastic_headloss

api = HydraulicAPI()
api.load_network_from_path('tutorials/mining_slurry_line/network.inp')

r_water = api.run_steady_state(save_plot=False)

wn = api.wn
for pid in list(wn.pipe_name_list)[:3]:
    pipe = wn.get_link(pid)
    fdata = r_water['flows'].get(pid, {})
    avg_lps = fdata.get('avg_flow_lps', 0)
    Q = abs(avg_lps) / 1000
    if Q > 0:
        hl_water = fdata.get('headloss_per_km', 0)
        r_slurry = bingham_plastic_headloss(
            flow_m3s=Q,
            diameter_m=pipe.diameter,
            length_m=pipe.length,
            density=1800,
            tau_y=15,
            mu_p=0.05,
            roughness_mm=0.1
        )
        hl_slurry = r_slurry['headloss_m'] / pipe.length * 1000
        ratio = hl_slurry / max(hl_water, 0.001)
        regime = r_slurry['regime']
        re = r_slurry['reynolds']
        print(pid + ': water=' + str(round(hl_water,2)) + ' m/km  slurry=' + str(round(hl_slurry,2)) + ' m/km  ratio=' + str(round(ratio,2)) + 'x')
        print('     regime=' + regime + '  Re=' + str(round(re)))
