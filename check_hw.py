from epanet_api import HydraulicAPI
import math

api = HydraulicAPI()
api.load_network_from_path('tutorials/mining_slurry_line/network.inp')
r = api.run_steady_state(save_plot=False)
pipe = api.wn.get_link('P1')

Q_wntr = api.steady_results.link['flowrate']['P1'].iloc[0]
HL_wntr = api.steady_results.link['headloss']['P1'].iloc[0]

print(f"P1: D={pipe.diameter} m, C={pipe.roughness}, L={pipe.length} m")
print(f"WNTR Q = {Q_wntr} m3/s")
print(f"WNTR Headloss raw = {HL_wntr}")

# Calculate HW by hand using the actual WNTR values
D = pipe.diameter
C = pipe.roughness
Q = Q_wntr
L = pipe.length

hw_headloss = 10.67 * L * abs(Q)**1.852 / (C**1.852 * D**4.87)
hw_per_km = hw_headloss / L * 1000

print(f"Hand calc HW (m/km): {hw_per_km}")

tool_hl_m = r['flows']['P1']['headloss_m'] if 'headloss_m' in r['flows']['P1'] else "N/A"
tool_hl_pkm = r['flows']['P1']['headloss_per_km'] if 'headloss_per_km' in r['flows']['P1'] else "N/A"

print(f"API returned dict headloss: {tool_hl_m} m, {tool_hl_pkm} m/km")
