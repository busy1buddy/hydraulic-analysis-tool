"""
Australian Suburban Water Distribution Network - Hydraulic Analysis
===================================================================
Uses WNTR (Water Network Tool for Resilience) with EPANET solver
All units in SI/Metric (LPS flow, metres head, mm diameters)
Suitable for Australian engineering practice
"""

import sys
import io
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import wntr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'models')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_analysis():
    # =========================================================================
    # 1. LOAD THE NETWORK MODEL
    # =========================================================================
    print("=" * 70)
    print("AUSTRALIAN SUBURBAN WATER NETWORK - HYDRAULIC ANALYSIS")
    print("=" * 70)

    inp_file = os.path.join(MODEL_DIR, 'australian_network.inp')
    wn = wntr.network.WaterNetworkModel(inp_file)

    print(f"\nNetwork Summary:")
    print(f"  Junctions:   {len(wn.junction_name_list)}")
    print(f"  Reservoirs:  {len(wn.reservoir_name_list)}")
    print(f"  Tanks:       {len(wn.tank_name_list)}")
    print(f"  Pipes:       {len(wn.pipe_name_list)}")
    print(f"  Flow units:  LPS (litres per second)")
    print(f"  Headloss:    Hazen-Williams")
    print(f"  Duration:    {wn.options.time.duration / 3600:.0f} hours")

    # =========================================================================
    # 2. PRINT NETWORK DETAILS
    # =========================================================================
    print(f"\n{'-' * 70}")
    print("JUNCTION DETAILS")
    print(f"{'-' * 70}")
    print(f"{'ID':<8} {'Elevation(m)':<14} {'Base Demand(LPS)':<18}")
    print(f"{'-' * 40}")
    for name in wn.junction_name_list:
        junc = wn.get_node(name)
        print(f"{name:<8} {junc.elevation:<14.1f} {junc.base_demand * 1000:<18.1f}")

    print(f"\n{'-' * 70}")
    print("PIPE DETAILS")
    print(f"{'-' * 70}")
    print(f"{'ID':<8} {'From':<8} {'To':<8} {'Length(m)':<12} {'Dia(mm)':<10} {'C':<8}")
    print(f"{'-' * 54}")
    for name in wn.pipe_name_list:
        pipe = wn.get_link(name)
        print(f"{name:<8} {pipe.start_node_name:<8} {pipe.end_node_name:<8} "
              f"{pipe.length:<12.0f} {pipe.diameter * 1000:<10.0f} {pipe.roughness:<8.0f}")

    # =========================================================================
    # 3. RUN EXTENDED PERIOD SIMULATION (24 hours)
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("RUNNING EXTENDED PERIOD SIMULATION (24 hours)")
    print(f"{'=' * 70}")

    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim()

    # =========================================================================
    # 4. RESULTS - PRESSURES
    # =========================================================================
    print(f"\n{'-' * 70}")
    print("JUNCTION PRESSURES (metres of head)")
    print(f"{'-' * 70}")

    pressures = results.node['pressure']
    junction_pressures = pressures[wn.junction_name_list]

    print(f"\n{'Junction':<10} {'Min(m)':<10} {'Max(m)':<10} {'Avg(m)':<10} {'Status'}")
    print(f"{'-' * 55}")
    for junc in wn.junction_name_list:
        p_min = junction_pressures[junc].min()
        p_max = junction_pressures[junc].max()
        p_avg = junction_pressures[junc].mean()
        # Australian standard: minimum 20m head at peak demand
        status = "OK" if p_min >= 20 else "LOW PRESSURE"
        print(f"{junc:<10} {p_min:<10.1f} {p_max:<10.1f} {p_avg:<10.1f} {status}")

    # =========================================================================
    # 5. RESULTS - FLOWS
    # =========================================================================
    print(f"\n{'-' * 70}")
    print("PIPE FLOWS (litres per second)")
    print(f"{'-' * 70}")

    flows = results.link['flowrate']
    pipe_flows = flows[wn.pipe_name_list]

    print(f"\n{'Pipe':<8} {'Min(LPS)':<12} {'Max(LPS)':<12} {'Avg(LPS)':<12} {'Velocity(m/s)'}")
    print(f"{'-' * 56}")
    for pipe_name in wn.pipe_name_list:
        pipe = wn.get_link(pipe_name)
        f_min = pipe_flows[pipe_name].min() * 1000  # m3/s to LPS
        f_max = pipe_flows[pipe_name].max() * 1000
        f_avg = pipe_flows[pipe_name].mean() * 1000
        # Calculate average velocity
        area = np.pi * (pipe.diameter / 2) ** 2
        v_avg = abs(pipe_flows[pipe_name].mean()) / area
        print(f"{pipe_name:<8} {f_min:<12.2f} {f_max:<12.2f} {f_avg:<12.2f} {v_avg:<12.2f}")

    # =========================================================================
    # 6. AUSTRALIAN COMPLIANCE CHECK
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("AUSTRALIAN STANDARDS COMPLIANCE CHECK")
    print(f"{'=' * 70}")

    issues = []

    # Check minimum pressure (WSAA standard: 20m at peak, 12m at fire flow)
    for junc in wn.junction_name_list:
        p_min = junction_pressures[junc].min()
        if p_min < 20:
            issues.append(f"  WARNING: {junc} min pressure {p_min:.1f}m < 20m (WSAA minimum)")
        elif p_min < 25:
            issues.append(f"  NOTE:    {junc} min pressure {p_min:.1f}m - close to 20m minimum")

    # Check maximum pressure (WSAA: typically < 50m static)
    for junc in wn.junction_name_list:
        p_max = junction_pressures[junc].max()
        if p_max > 50:
            issues.append(f"  WARNING: {junc} max pressure {p_max:.1f}m > 50m (consider PRV)")

    # Check velocities (Australian guideline: 0.5 - 2.0 m/s in mains)
    for pipe_name in wn.pipe_name_list:
        pipe = wn.get_link(pipe_name)
        area = np.pi * (pipe.diameter / 2) ** 2
        v_max = abs(pipe_flows[pipe_name].max()) / area
        if v_max > 2.0:
            issues.append(f"  WARNING: {pipe_name} velocity {v_max:.2f} m/s > 2.0 m/s limit")
        elif v_max < 0.3 and pipe_flows[pipe_name].mean() > 0:
            issues.append(f"  NOTE:    {pipe_name} low velocity {v_max:.2f} m/s (stagnation risk)")

    if issues:
        print("\nIssues Found:")
        for issue in issues:
            print(issue)
    else:
        print("\n  All parameters within Australian standards (WSAA guidelines)")

    # =========================================================================
    # 7. GENERATE PLOTS
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("GENERATING PLOTS")
    print(f"{'=' * 70}")

    # Plot 1: Pressure profiles over 24 hours
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Australian Suburban Network - 24hr Hydraulic Analysis', fontsize=14, fontweight='bold')

    # Pressure over time
    ax1 = axes[0, 0]
    hours = junction_pressures.index / 3600
    for junc in wn.junction_name_list:
        ax1.plot(hours, junction_pressures[junc], label=junc, linewidth=1.5)
    ax1.axhline(y=20, color='red', linestyle='--', alpha=0.7, label='Min 20m (WSAA)')
    ax1.set_xlabel('Time (hours)')
    ax1.set_ylabel('Pressure (m)')
    ax1.set_title('Junction Pressures Over 24 Hours')
    ax1.legend(fontsize=8, ncol=2)
    ax1.grid(True, alpha=0.3)

    # Flow over time
    ax2 = axes[0, 1]
    for pipe_name in wn.pipe_name_list:
        ax2.plot(hours, pipe_flows[pipe_name] * 1000, label=pipe_name, linewidth=1.5)
    ax2.set_xlabel('Time (hours)')
    ax2.set_ylabel('Flow (LPS)')
    ax2.set_title('Pipe Flows Over 24 Hours')
    ax2.legend(fontsize=8, ncol=2)
    ax2.grid(True, alpha=0.3)

    # Network layout with pressures at peak hour
    ax3 = axes[1, 0]
    # Find peak demand hour (hour with lowest avg pressure)
    peak_idx = junction_pressures.mean(axis=1).idxmin()
    peak_hour = peak_idx / 3600

    node_coords = {}
    for name in list(wn.junction_name_list) + list(wn.reservoir_name_list) + list(wn.tank_name_list):
        node = wn.get_node(name)
        node_coords[name] = node.coordinates

    # Draw pipes
    for pipe_name in wn.pipe_name_list:
        pipe = wn.get_link(pipe_name)
        x1, y1 = node_coords[pipe.start_node_name]
        x2, y2 = node_coords[pipe.end_node_name]
        ax3.plot([x1, x2], [y1, y2], 'b-', linewidth=max(1, pipe.diameter * 1000 / 100), alpha=0.6)

    # Draw nodes with pressure coloring
    for name in wn.junction_name_list:
        x, y = node_coords[name]
        p = pressures[name].loc[peak_idx]
        color = 'green' if p >= 20 else 'red'
        ax3.scatter(x, y, c=color, s=80, zorder=5, edgecolors='black')
        ax3.annotate(f'{name}\n{p:.0f}m', (x, y), textcoords="offset points",
                    xytext=(5, 5), fontsize=7)

    for name in wn.reservoir_name_list:
        x, y = node_coords[name]
        ax3.scatter(x, y, c='blue', s=120, marker='s', zorder=5, edgecolors='black')
        ax3.annotate(name, (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8)

    for name in wn.tank_name_list:
        x, y = node_coords[name]
        ax3.scatter(x, y, c='cyan', s=120, marker='D', zorder=5, edgecolors='black')
        ax3.annotate(name, (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8)

    ax3.set_title(f'Network Layout - Pressures at Peak Hour ({peak_hour:.0f}:00)')
    ax3.set_xlabel('X (m)')
    ax3.set_ylabel('Y (m)')
    ax3.grid(True, alpha=0.3)

    # Tank level
    ax4 = axes[1, 1]
    tank_pressure = pressures['T1'] if 'T1' in pressures.columns else None
    if tank_pressure is not None:
        ax4.plot(hours, tank_pressure, 'c-', linewidth=2, label='T1 Level')
        ax4.set_xlabel('Time (hours)')
        ax4.set_ylabel('Tank Level (m)')
        ax4.set_title('Elevated Tank T1 - Water Level')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, 'hydraulic_results.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {plot_path}")

    # =========================================================================
    # 8. SUMMARY TABLE
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("SIMULATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Network file:  {inp_file}")
    print(f"  Solver:        EPANET via WNTR {wntr.__version__}")
    print(f"  Duration:      24 hours")
    print(f"  Timestep:      1 hour")
    print(f"  Total demand:  {sum(wn.get_node(j).base_demand for j in wn.junction_name_list) * 1000:.1f} LPS base")

    return wn, results


if __name__ == '__main__':
    wn, results = run_analysis()
