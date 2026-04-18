import matplotlib.pyplot as plt
import numpy as np
from epanet_api import HydraulicAPI

# Setup API and data
api = HydraulicAPI()
api.load_network_from_path('tutorials/brine_pipeline/network.inp')
res = api.run_steady_state()

path_nodes = ['R1', 'J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8']
chainage = []
inverts = []
hgl = []
current_chainage = 0.0
pressures = res.get('pressures', {})

for i, nid in enumerate(path_nodes):
    node = api.wn.get_node(nid)
    # Get true node elevation (invert)
    elev = getattr(node, 'elevation', getattr(node, 'base_head', 0.0))
    inverts.append(elev)
    
    p_data = pressures.get(nid, {})
    p = p_data.get('avg_m', 0.0)
    hgl.append(elev + p)
    
    if i == 0:
        chainage.append(0.0)
    else:
        # find link length
        prev_nid = path_nodes[i-1]
        link_id = None
        for l in api.wn.get_links_for_node(prev_nid):
            lnk = api.wn.get_link(l)
            if lnk.start_node_name == nid or lnk.end_node_name == nid:
                link_id = l
                break
        link = api.wn.get_link(link_id)
        current_chainage += getattr(link, 'length', 0.0)
        chainage.append(current_chainage)

# Detect Scour points (local minima in invert profile)
scour_points = []
av_points = []
for i in range(1, len(inverts)-1):
    # Air valves at local peaks
    if inverts[i] > inverts[i-1] and inverts[i] > inverts[i+1]:
        av_points.append({'chainage': chainage[i], 'elevation': inverts[i], 'label': 'Air/Vacuum Valve'})
    # Scour valves at local dips
    elif inverts[i] < inverts[i-1] and inverts[i] < inverts[i+1]:
        scour_points.append({'chainage': chainage[i], 'elevation': inverts[i], 'label': 'Scour Valve'})

# Create plot
plt.figure(figsize=(14, 8))

# Plot Terrain / Invert
plt.fill_between(chainage, 0, inverts, color='#8B4513', alpha=0.5, label='Terrain / Ground')
plt.plot(chainage, inverts, color='#4A2A14', linewidth=4, label='Pipeline Invert (DN125 PN10)')

# Plot HGL
plt.plot(chainage, hgl, color='#00CED1', linewidth=3, linestyle='-', label='Hydraulic Grade Line (Brine SG=1.15)')
plt.fill_between(chainage, inverts, hgl, color='#E0FFFF', alpha=0.4, label='Water Pressure (Head)')

# Plot Air Valves
for i, av in enumerate(av_points):
    c = av['chainage']
    e = av['elevation']
    plt.plot(c, e, '^', markersize=14, color='#FFA500', markeredgecolor='black', label='Air/Vacuum Valve' if i==0 else "")
    plt.annotate(av['label'], (c, e), textcoords='offset points', xytext=(0, 20), ha='center', fontsize=10, weight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.9),
                 arrowprops=dict(arrowstyle='-', color='black'))

# Plot Scour Valves
for i, scour in enumerate(scour_points):
    c = scour['chainage']
    e = scour['elevation']
    plt.plot(c, e, 'v', markersize=14, color='#32CD32', markeredgecolor='black', label='Scour Valve' if i==0 else "")
    plt.annotate(scour['label'], (c, e), textcoords='offset points', xytext=(0, -25), ha='center', fontsize=10, weight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.9),
                 arrowprops=dict(arrowstyle='-', color='black'))

# Start and End markers
plt.plot(chainage[0], hgl[0], 's', markersize=12, color='blue', markeredgecolor='black', label='Brine Source (Pump Head)')
plt.annotate(f'HGL: {hgl[0]:.1f}m\nElev: {inverts[0]:.1f}m', (chainage[0], hgl[0]), textcoords='offset points', xytext=(-20, 20), ha='center', color='blue', weight='bold')

end_idx = len(chainage)-1
plt.plot(chainage[end_idx], hgl[end_idx], 'o', markersize=10, color='red', markeredgecolor='black', label='Discharge')
plt.annotate(f'Terminal HGL: {hgl[end_idx]:.1f}m\nElev: {inverts[end_idx]:.1f}m', (chainage[end_idx], hgl[end_idx]), textcoords='offset points', xytext=(20, 20), ha='center', color='red', weight='bold')

plt.title('DN125 PN10 Brine Transfer Pipeline: Invert Profile & Hydraulic Grade Line', fontsize=16, pad=15)
plt.xlabel('Distance / Chainage (m)', fontsize=13)
plt.ylabel('Elevation (m AHD)', fontsize=13)
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend(loc='lower left', fontsize=11, framealpha=0.95)
plt.ylim(0, max(max(hgl), max(inverts)) + 20)
plt.xlim(-200, max(chainage) + 200)
plt.tight_layout()

# Save plot
plt.savefig('output_brine_pipeline.png', dpi=300)
print('Successfully generated plot: output_brine_pipeline.png')