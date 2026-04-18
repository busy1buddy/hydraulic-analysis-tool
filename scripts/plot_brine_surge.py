import matplotlib.pyplot as plt
from tsnet.network import TransientModel
from tsnet.simulation import Initializer, MOCSimulator
import numpy as np

# Load the temp model
tm = TransientModel('temp_brine.inp')
tm.set_wavespeed(400) # PE pipe has ~400m/s wavespeed
tm.set_time(30) # 30 seconds simulation

# Pump trip rule: close over 2 seconds starting at t=1s
tm.pump_shut_off('PU1', [2.0, 1.0, 0, 1])

# Initialize and simulate
tm = Initializer(tm, 0, engine='DD')
tm = MOCSimulator(tm)

# Plot pressure at J1 (Pump discharge) and J2 (High point) over time
t = tm.simulation_timestamps
j1 = tm.get_node('J1')
j2 = tm.get_node('J2')

p_j1 = j1.head - j1.elevation
p_j2 = j2.head - j2.elevation

plt.figure(figsize=(10, 6))
plt.plot(t, p_j1, label='J1 (Pump Discharge, Elev 20m)', color='blue', linewidth=2)
plt.plot(t, p_j2, label='J2 (High Point 1, Elev 45m)', color='orange', linewidth=2)

plt.axhline(0, color='red', linestyle='--', label='Vacuum / Column Separation Risk (0m Gauge)')

plt.title('Transient Surge Analysis: Sudden Pump Trip (DN125 PE Pipe)', fontsize=14)
plt.xlabel('Time (seconds)', fontsize=12)
plt.ylabel('Gauge Pressure Head (m Brine)', fontsize=12)
plt.legend()
plt.grid(True, linestyle=':', alpha=0.7)
plt.tight_layout()

# Save plot
plt.savefig('output_brine_surge.png', dpi=300)
print('Successfully generated plot: output_brine_surge.png')
