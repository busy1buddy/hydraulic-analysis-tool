"""
Hydraulic Shock (Water Hammer) Transient Analysis
==================================================
Uses TSNet with Method of Characteristics (MOC) solver
Simulates sudden valve closure causing pressure transients
Australian engineering context - SI/metric units

Water hammer scenario: Sudden valve closure at end-of-line pipe
causing pressure wave propagation through the network.
"""

import sys
import io
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import wntr
import tsnet
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'models')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def create_transient_network():
    """
    Create a purpose-built network for transient analysis.
    TSNet requires specific network topology - a simpler linear network
    works best for demonstrating water hammer phenomena.
    """
    inp_file = os.path.join(MODEL_DIR, 'transient_network.inp')

    inp_content = """[TITLE]
Water Hammer Analysis - Valve Closure Transient
Australian conditions - SI/Metric (LPS)

[JUNCTIONS]
;ID              Elev            Demand          Pattern
 J1              50              0                               ;  Upstream junction
 J2              48              2.0                             ;  Mid-point junction
 J3              45              5.0                             ;  Downstream junction
 J4              42              3.0                             ;  Branch junction
 J5              40              0                               ;  Valve upstream node
 J6              40              8.0                             ;  Downstream demand node

[RESERVOIRS]
;ID              Head            Pattern
 R1              80                                              ;  Source reservoir

[TANKS]

[PIPES]
;ID              Node1           Node2           Length          Diameter        Roughness       MinorLoss       Status
 P1              R1              J1              800             300             130             0               Open
 P2              J1              J2              600             250             130             0               Open
 P3              J2              J3              500             200             120             0               Open
 P4              J2              J4              400             150             120             0               Open
 P5              J3              J5              300             200             120             0               Open
 P6              J6              J4              200             150             120             0               Open

[PUMPS]

[VALVES]
;ID              Node1           Node2           Diameter        Type            Setting         MinorLoss
 V1              J5              J6              200             TCV             1               0

[PATTERNS]

[CURVES]

[CONTROLS]

[RULES]

[ENERGY]
 Global Efficiency  	75
 Global Price       	0.25

[TIMES]
 Duration            0:00
 Hydraulic Timestep  1:00
 Quality Timestep    0:05
 Pattern Timestep    1:00

[REPORT]
 Status              No
 Summary             No

[OPTIONS]
 Units               LPS
 Headloss            H-W
 Specific Gravity    1
 Viscosity           1
 Trials              40
 Accuracy            0.001
 Unbalanced          Continue 10
 Demand Multiplier   1.0

[COORDINATES]
;Node            X-Coord            Y-Coord
 R1              0.00               50.00
 J1              20.00              50.00
 J2              35.00              48.00
 J3              50.00              45.00
 J4              35.00              60.00
 J5              60.00              42.00
 J6              70.00              42.00

[END]
"""

    with open(inp_file, 'w') as f:
        f.write(inp_content)

    return inp_file


def run_transient_analysis():
    print("=" * 70)
    print("HYDRAULIC SHOCK (WATER HAMMER) TRANSIENT ANALYSIS")
    print("=" * 70)

    # =========================================================================
    # 1. CREATE TRANSIENT NETWORK
    # =========================================================================
    inp_file = create_transient_network()
    print(f"\n  Network file: {inp_file}")

    # =========================================================================
    # 2. LOAD INTO TSNET
    # =========================================================================
    print(f"\n{'-' * 70}")
    print("LOADING NETWORK INTO TSNet MOC SOLVER")
    print(f"{'-' * 70}")

    tm = tsnet.network.TransientModel(inp_file)

    # Set wave speed for all pipes and valves (m/s)
    # Typical values for ductile iron/PVC pipes in Australian water mains:
    # - Ductile iron: 1000-1200 m/s
    # - PVC: 300-500 m/s
    # - Steel: 900-1200 m/s
    wave_speed = 1000  # m/s
    tm.set_wavespeed(wave_speed)

    n_pipes = len(tm.pipe_name_list)
    n_valves = len(tm.valve_name_list)
    print(f"  Wave speed set: {wave_speed} m/s (ductile iron pipe)")
    print(f"  Pipes: {n_pipes}")
    print(f"  Valves: {n_valves} ({', '.join(tm.valve_name_list)})")
    print(f"  Junctions: {len(tm.junction_name_list)}")

    # =========================================================================
    # 3. DEFINE TRANSIENT EVENT - SUDDEN VALVE CLOSURE
    # =========================================================================
    print(f"\n{'-' * 70}")
    print("TRANSIENT EVENT: VALVE V1 CLOSURE (BETWEEN J5-J6)")
    print(f"{'-' * 70}")

    # Simulation parameters
    t_total = 20       # Total simulation time (seconds)

    # Valve closure rule: [tc, ts, se, m]
    # tc = closure duration (seconds)
    # ts = closure start time (seconds)
    # se = final open percentage (0 = fully closed)
    # m  = closure constant (1 = linear, 2 = quadratic)
    closure_time = 0.5   # seconds - rapid closure (water hammer condition)
    start_time = 2.0     # start closure at t=2s
    final_open = 0.0     # fully closed
    closure_shape = 1    # linear closure profile

    print(f"  Valve:             V1 (TCV between J5 and J6)")
    print(f"  Closure time:      {closure_time} seconds (rapid)")
    print(f"  Closure starts at: {start_time} seconds")
    print(f"  Closure profile:   Linear (m={closure_shape})")
    print(f"  Simulation time:   {t_total} seconds")

    # Set simulation time (TSNet calculates optimal dt from wave speed)
    tm.set_time(t_total)

    # Define the valve closure operation
    valve_rule = [closure_time, start_time, final_open, closure_shape]
    tm.valve_closure('V1', valve_rule)

    print(f"  Computed time step: {tm.time_step:.5f} seconds")
    print(f"\n  Valve closure defined. Running MOC transient solver...")

    # =========================================================================
    # 4. RUN TRANSIENT SIMULATION
    # =========================================================================
    print(f"\n{'-' * 70}")
    print("RUNNING METHOD OF CHARACTERISTICS (MOC) SOLVER")
    print(f"{'-' * 70}")

    # Step 1: Initialize steady-state conditions using EPANET
    t0 = 0  # initial time for steady-state calc
    tm = tsnet.simulation.Initializer(tm, t0, engine='DD')

    # Step 2: Run MOC transient simulation
    tm = tsnet.simulation.MOCSimulator(tm)

    print("  Simulation complete!")

    # =========================================================================
    # 5. EXTRACT AND REPORT RESULTS
    # =========================================================================
    print(f"\n{'-' * 70}")
    print("TRANSIENT RESULTS")
    print(f"{'-' * 70}")

    # Get results at key nodes
    node_results = {}
    for node_name in tm.junction_name_list:
        node = tm.get_node(node_name)
        node_results[node_name] = {
            'head': node.head,
            'elevation': node.elevation
        }

    # Get pipe results (pipes only, not valves)
    pipe_results = {}
    for pipe_name in tm.pipe_name_list:
        pipe = tm.get_link(pipe_name)
        pipe_results[pipe_name] = {
            'start_velocity': pipe.start_node_velocity,
            'end_velocity': pipe.end_node_velocity,
            'start_head': pipe.start_node_head,
            'end_head': pipe.end_node_head
        }

    # Time array
    t = tm.simulation_timestamps

    # Calculate Joukowsky pressure rise
    # Delta_H = (a * Delta_V) / g
    # where a = wave speed, Delta_V = velocity change, g = gravity
    g = 9.81  # m/s²

    print(f"\n  Joukowsky Equation: dH = (a x dV) / g")
    print(f"  Wave speed (a): {wave_speed} m/s")
    print(f"  Gravity (g):    {g} m/s^2")

    print(f"\n{'Junction':<10} {'Steady Head(m)':<16} {'Max Head(m)':<14} {'Min Head(m)':<14} {'dH(m)':<10} {'dP(kPa)'}")
    print(f"{'-' * 78}")

    for node_name in tm.junction_name_list:
        head = node_results[node_name]['head']
        elev = node_results[node_name]['elevation']
        steady_head = head[0]
        max_head = np.max(head)
        min_head = np.min(head)
        delta_h = max_head - steady_head
        delta_p = delta_h * g  # Convert m of head to kPa (approximately)

        print(f"{node_name:<10} {steady_head:<16.1f} {max_head:<14.1f} {min_head:<14.1f} "
              f"{delta_h:<10.1f} {delta_p:<10.1f}")

    # =========================================================================
    # 6. AUSTRALIAN ENGINEERING ASSESSMENT
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("AUSTRALIAN ENGINEERING ASSESSMENT")
    print(f"{'=' * 70}")

    # Check pipe ratings (typical Australian ductile iron: PN35 = 3500 kPa)
    pipe_rating_kPa = 3500  # PN35 ductile iron (common in AU)
    pipe_rating_m = pipe_rating_kPa / g

    print(f"\n  Pipe rating: PN35 ({pipe_rating_kPa} kPa = {pipe_rating_m:.0f}m head)")

    for node_name in tm.junction_name_list:
        head = node_results[node_name]['head']
        max_head = np.max(head)
        max_pressure_kPa = max_head * g

        if max_pressure_kPa > pipe_rating_kPa:
            print(f"  CRITICAL: {node_name} max transient pressure {max_pressure_kPa:.0f} kPa "
                  f"EXCEEDS PN35 rating!")
        elif max_pressure_kPa > pipe_rating_kPa * 0.8:
            print(f"  WARNING:  {node_name} max transient pressure {max_pressure_kPa:.0f} kPa "
                  f"exceeds 80% of PN35")
        else:
            print(f"  OK:       {node_name} max transient pressure {max_pressure_kPa:.0f} kPa "
                  f"within PN35 rating")

    # Check for negative pressures (vapour pressure / column separation)
    for node_name in tm.junction_name_list:
        head = node_results[node_name]['head']
        elev = node_results[node_name]['elevation']
        min_pressure_head = np.min(head) - elev
        if min_pressure_head < 0:
            print(f"  CRITICAL: {node_name} negative pressure detected ({min_pressure_head:.1f}m) "
                  f"- column separation risk!")
        elif min_pressure_head < 5:
            print(f"  WARNING:  {node_name} very low pressure ({min_pressure_head:.1f}m) "
                  f"- intrusion risk")

    # =========================================================================
    # 7. GENERATE TRANSIENT PLOTS
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("GENERATING TRANSIENT PLOTS")
    print(f"{'=' * 70}")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Water Hammer Analysis - Sudden Valve Closure\n'
                 f'Wave Speed: {wave_speed} m/s | Closure Time: {closure_time}s | '
                 f'Pipe Rating: PN35',
                 fontsize=12, fontweight='bold')

    # Plot 1: Head at all junctions over time
    ax1 = axes[0, 0]
    for node_name in tm.junction_name_list:
        head = node_results[node_name]['head']
        ax1.plot(t, head, label=node_name, linewidth=1.2)
    ax1.axhline(y=80, color='blue', linestyle=':', alpha=0.5, label='Reservoir Head')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Head (m)')
    ax1.set_title('Hydraulic Head at Junctions')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Plot 2: Head at valve location (J5 upstream of valve) - detailed
    ax2 = axes[0, 1]
    valve_node = 'J5'  # upstream of valve V1
    head_valve = node_results[valve_node]['head']
    ax2.plot(t, head_valve, 'r-', linewidth=1.5, label=f'{valve_node} (upstream of V1)')
    if 'J6' in node_results:
        ax2.plot(t, node_results['J6']['head'], 'b-', linewidth=1.2, label='J6 (downstream of V1)')
    steady = head_valve[0]
    ax2.axhline(y=steady, color='gray', linestyle='--', alpha=0.7, label=f'Steady state: {steady:.1f}m')
    ax2.axhline(y=pipe_rating_m, color='orange', linestyle='--', alpha=0.7,
               label=f'PN35 rating: {pipe_rating_m:.0f}m')
    ax2.axvline(x=start_time, color='green', linestyle=':', alpha=0.7, label='Valve closure start')
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Head (m)')
    ax2.set_title('Head at Valve V1 - Water Hammer Detail')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Velocity in pipe P5 (upstream of valve)
    ax3 = axes[1, 0]
    v_start = pipe_results['P5']['start_velocity']
    v_end = pipe_results['P5']['end_velocity']
    ax3.plot(t, v_start, 'b-', linewidth=1.2, label='P5 start (at J3)')
    ax3.plot(t, v_end, 'r-', linewidth=1.2, label='P5 end (at J5/valve)')
    ax3.axvline(x=start_time, color='green', linestyle=':', alpha=0.7, label='Valve closure start')
    ax3.set_xlabel('Time (seconds)')
    ax3.set_ylabel('Velocity (m/s)')
    ax3.set_title('Flow Velocity in Pipe P5 (Upstream of Valve)')
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)

    # Plot 4: Pressure envelope (max/min along network)
    ax4 = axes[1, 1]
    positions = []
    max_heads = []
    min_heads = []
    steady_heads = []
    labels = []

    for i, node_name in enumerate(tm.junction_name_list):
        head = node_results[node_name]['head']
        positions.append(i)
        max_heads.append(np.max(head))
        min_heads.append(np.min(head))
        steady_heads.append(head[0])
        labels.append(node_name)

    ax4.fill_between(positions, min_heads, max_heads, alpha=0.3, color='red',
                    label='Transient envelope')
    ax4.plot(positions, steady_heads, 'bo-', linewidth=2, label='Steady state')
    ax4.plot(positions, max_heads, 'r^-', linewidth=1, label='Max transient')
    ax4.plot(positions, min_heads, 'rv-', linewidth=1, label='Min transient')
    ax4.set_xticks(positions)
    ax4.set_xticklabels(labels)
    ax4.set_xlabel('Junction')
    ax4.set_ylabel('Head (m)')
    ax4.set_title('Pressure Envelope - Steady vs Transient')
    ax4.legend(fontsize=8)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, 'transient_results.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {plot_path}")

    # =========================================================================
    # 8. MITIGATION RECOMMENDATIONS
    # =========================================================================
    print(f"\n{'=' * 70}")
    print("MITIGATION RECOMMENDATIONS (AUSTRALIAN PRACTICE)")
    print(f"{'=' * 70}")

    max_surge = max(np.max(node_results[n]['head']) - node_results[n]['head'][0]
                    for n in tm.junction_name_list)
    max_surge_kPa = max_surge * g

    print(f"\n  Maximum surge: {max_surge:.1f}m ({max_surge_kPa:.0f} kPa)")
    print()

    if max_surge > 50:
        print("  1. SURGE VESSELS: Install air/vacuum vessels at critical points")
        print("     - Size per AS/NZS 2566 or WSAA guidelines")
        print("  2. SLOW-CLOSING VALVES: Replace with actuated valves (>10s closure)")
        print("  3. PRESSURE RELIEF VALVES: Install at high-risk locations")
        print("  4. NON-RETURN VALVES: With controlled closure characteristics")
    elif max_surge > 20:
        print("  1. SLOW-CLOSING VALVES: Extend closure time to >5 seconds")
        print("  2. Consider surge anticipation valves at key junctions")
        print("  3. Review pipe class ratings with safety factor")
    else:
        print("  Surge within acceptable limits for standard pipe ratings")
        print("  Standard operating procedures sufficient")

    print(f"\n{'=' * 70}")
    print("TRANSIENT ANALYSIS COMPLETE")
    print(f"{'=' * 70}")

    return tm


if __name__ == '__main__':
    tm = run_transient_analysis()
