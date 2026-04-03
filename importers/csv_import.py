"""
CSV Network Importer
=====================
Import water network models from two CSV files:
- nodes.csv: id, type, x, y, elevation, demand, head
- pipes.csv: id, start, end, length, diameter, roughness, type

This is the simplest import path and should be implemented first.
"""

import os
import csv
import wntr


def import_from_csv(nodes_csv, pipes_csv, output_name='imported_network',
                    output_dir=None, duration_hrs=24):
    """
    Import a water network from CSV files.

    Parameters
    ----------
    nodes_csv : str
        Path to nodes CSV file. Required columns: id, type, x, y, elevation.
        Optional: demand (LPS), head (m for reservoirs).
        type values: junction, reservoir, tank
    pipes_csv : str
        Path to pipes CSV file. Required columns: id, start, end, length, diameter.
        Optional: roughness (default 130), type (pipe/valve, default pipe).
    output_name : str
        Name for the output .inp file (without extension).
    output_dir : str
        Directory to save the .inp file. Defaults to models/ in project root.
    duration_hrs : int
        Simulation duration in hours.

    Returns
    -------
    dict with network summary and output path.
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'models')
    os.makedirs(output_dir, exist_ok=True)

    wn = wntr.network.WaterNetworkModel()

    # Parse nodes
    nodes_added = {'junction': 0, 'reservoir': 0, 'tank': 0}
    with open(nodes_csv, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            node_id = row['id'].strip()
            node_type = row.get('type', 'junction').strip().lower()
            x = float(row.get('x', 0))
            y = float(row.get('y', 0))

            if node_type == 'reservoir':
                head = float(row.get('head', row.get('elevation', 80)))
                wn.add_reservoir(node_id, base_head=head, coordinates=(x, y))
                nodes_added['reservoir'] += 1

            elif node_type == 'tank':
                elev = float(row.get('elevation', 50))
                wn.add_tank(node_id, elevation=elev,
                           init_level=float(row.get('init_level', 3)),
                           min_level=float(row.get('min_level', 0.5)),
                           max_level=float(row.get('max_level', 5)),
                           diameter=float(row.get('tank_diameter', 10)),
                           coordinates=(x, y))
                nodes_added['tank'] += 1

            else:  # junction
                elev = float(row.get('elevation', 0))
                demand = float(row.get('demand', 0)) / 1000  # LPS to m3/s
                wn.add_junction(node_id, elevation=elev, base_demand=demand,
                               coordinates=(x, y))
                nodes_added['junction'] += 1

    # Parse pipes/valves
    links_added = {'pipe': 0, 'valve': 0}
    with open(pipes_csv, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            link_id = row['id'].strip()
            start = row['start'].strip()
            end = row['end'].strip()
            length = float(row.get('length', 100))
            diameter = float(row.get('diameter', 200)) / 1000  # mm to m
            roughness = float(row.get('roughness', 130))
            link_type = row.get('type', 'pipe').strip().lower()

            if link_type == 'valve':
                valve_type = row.get('valve_type', 'TCV')
                setting = float(row.get('setting', 1))
                wn.add_valve(link_id, start, end, diameter=diameter,
                            valve_type=valve_type, initial_setting=setting)
                links_added['valve'] += 1
            else:
                wn.add_pipe(link_id, start, end, length=length,
                           diameter=diameter, roughness=roughness)
                links_added['pipe'] += 1

    # Set simulation options
    wn.options.time.duration = duration_hrs * 3600
    wn.options.time.hydraulic_timestep = 3600
    wn.options.time.report_timestep = 3600

    # Save
    output_path = os.path.join(output_dir, f'{output_name}.inp')
    wntr.network.write_inpfile(wn, output_path)

    return {
        'output_file': output_path,
        'nodes': nodes_added,
        'links': links_added,
        'total_nodes': sum(nodes_added.values()),
        'total_links': sum(links_added.values()),
    }


def create_sample_csvs(output_dir):
    """Create sample CSV files for testing the import."""
    os.makedirs(output_dir, exist_ok=True)

    nodes_path = os.path.join(output_dir, 'sample_nodes.csv')
    with open(nodes_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'type', 'x', 'y', 'elevation', 'demand', 'head'])
        writer.writerow(['R1', 'reservoir', 0, 50, 80, 0, 80])
        writer.writerow(['J1', 'junction', 15, 50, 50, 0, ''])
        writer.writerow(['J2', 'junction', 30, 45, 45, 8, ''])
        writer.writerow(['J3', 'junction', 45, 40, 42, 12, ''])
        writer.writerow(['J4', 'junction', 30, 55, 48, 5, ''])

    pipes_path = os.path.join(output_dir, 'sample_pipes.csv')
    with open(pipes_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'start', 'end', 'length', 'diameter', 'roughness', 'type'])
        writer.writerow(['P1', 'R1', 'J1', 500, 300, 130, 'pipe'])
        writer.writerow(['P2', 'J1', 'J2', 400, 250, 130, 'pipe'])
        writer.writerow(['P3', 'J2', 'J3', 350, 200, 120, 'pipe'])
        writer.writerow(['P4', 'J1', 'J4', 300, 200, 130, 'pipe'])
        writer.writerow(['P5', 'J4', 'J2', 250, 150, 120, 'pipe'])

    return nodes_path, pipes_path
