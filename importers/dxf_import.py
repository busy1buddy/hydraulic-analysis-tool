"""
DXF/CAD Network Importer
==========================
Import water network models from DXF/CAD files.
Requires ezdxf.

Uses layer naming conventions:
- PIPES or WATER_MAINS: polylines as pipes
- JUNCTIONS or NODES: points/circles as junctions
- RESERVOIRS: points as reservoirs
- TANKS: points as tanks
"""

import os
import warnings
import math


def import_from_dxf(dxf_file, output_name='dxf_network', output_dir=None,
                    default_diameter=200, default_roughness=130,
                    default_elevation=40, duration_hrs=24,
                    pipe_layers=None, junction_layers=None,
                    reservoir_layers=None):
    """
    Import a water network from a DXF file.

    Parameters
    ----------
    dxf_file : str
        Path to DXF file.
    output_name : str
        Name for the output .inp file.
    output_dir : str
        Directory to save the .inp file.
    default_diameter : float
        Default pipe diameter in mm (DXF usually lacks hydraulic data).
    default_roughness : float
        Default Hazen-Williams C-factor.
    default_elevation : float
        Default junction elevation in metres.
    pipe_layers : list
        Layer names containing pipe geometry. Default: ['PIPES', 'WATER_MAINS', 'MAINS'].
    junction_layers : list
        Layer names containing junction points. Default: ['JUNCTIONS', 'NODES'].
    reservoir_layers : list
        Layer names for reservoirs. Default: ['RESERVOIRS', 'SOURCES'].

    Returns
    -------
    dict with network summary and output path.
    """
    try:
        import ezdxf
    except ImportError:
        return {'error': 'ezdxf is required for DXF import. '
                'Install with: pip install ezdxf'}

    import wntr

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'models')
    os.makedirs(output_dir, exist_ok=True)

    pipe_layers = pipe_layers or ['PIPES', 'WATER_MAINS', 'MAINS', 'pipes', 'water_mains']
    junction_layers = junction_layers or ['JUNCTIONS', 'NODES', 'junctions', 'nodes']
    reservoir_layers = reservoir_layers or ['RESERVOIRS', 'SOURCES', 'reservoirs', 'sources']

    doc = ezdxf.readfile(dxf_file)
    msp = doc.modelspace()

    wn = wntr.network.WaterNetworkModel()
    nodes_added = {'junction': 0, 'reservoir': 0}
    links_added = {'pipe': 0}
    node_coords = {}  # (x, y) -> node_id
    snap_tolerance = 0.5  # metres

    def _get_or_create_node(x, y, node_type='junction'):
        """Get existing node at coords or create a new one."""
        for (nx, ny), nid in node_coords.items():
            if math.hypot(x - nx, y - ny) < snap_tolerance:
                return nid

        if node_type == 'reservoir':
            nid = f'R{nodes_added["reservoir"] + 1}'
            wn.add_reservoir(nid, base_head=80, coordinates=(x, y))
            nodes_added['reservoir'] += 1
        else:
            nid = f'J{nodes_added["junction"] + 1}'
            wn.add_junction(nid, elevation=default_elevation,
                           base_demand=0, coordinates=(x, y))
            nodes_added['junction'] += 1

        node_coords[(x, y)] = nid
        return nid

    # Process explicit node entities (points, circles)
    for entity in msp:
        layer = entity.dxf.layer.upper() if hasattr(entity.dxf, 'layer') else ''

        if entity.dxftype() in ('POINT', 'CIRCLE', 'INSERT'):
            if hasattr(entity.dxf, 'insert'):
                x, y = entity.dxf.insert.x, entity.dxf.insert.y
            elif hasattr(entity.dxf, 'center'):
                x, y = entity.dxf.center.x, entity.dxf.center.y
            else:
                continue

            if any(l.upper() in layer for l in reservoir_layers):
                _get_or_create_node(x, y, 'reservoir')
            elif any(l.upper() in layer for l in junction_layers):
                _get_or_create_node(x, y, 'junction')

    # Process pipe entities (lines, polylines, lwpolylines)
    for entity in msp:
        layer = entity.dxf.layer.upper() if hasattr(entity.dxf, 'layer') else ''

        if not any(l.upper() in layer for l in pipe_layers):
            continue

        points = []
        if entity.dxftype() == 'LINE':
            points = [(entity.dxf.start.x, entity.dxf.start.y),
                      (entity.dxf.end.x, entity.dxf.end.y)]
        elif entity.dxftype() == 'LWPOLYLINE':
            points = [(p[0], p[1]) for p in entity.get_points()]
        elif entity.dxftype() == 'POLYLINE':
            points = [(v.dxf.location.x, v.dxf.location.y)
                      for v in entity.vertices]

        if len(points) < 2:
            continue

        # Create pipe for each segment
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]

            start_node = _get_or_create_node(x1, y1)
            end_node = _get_or_create_node(x2, y2)

            if start_node == end_node:
                continue

            length = math.hypot(x2 - x1, y2 - y1)
            if length < 0.1:
                continue

            pipe_id = f'P{links_added["pipe"] + 1}'
            try:
                wn.add_pipe(pipe_id, start_node, end_node, length=length,
                           diameter=default_diameter / 1000,
                           roughness=default_roughness)
                links_added['pipe'] += 1
            except Exception as e:
                warnings.warn(f'Skipping pipe {pipe_id}: {e}')

    # Set simulation options
    wn.options.time.duration = duration_hrs * 3600
    wn.options.time.hydraulic_timestep = 3600

    output_path = os.path.join(output_dir, f'{output_name}.inp')
    wntr.network.write_inpfile(wn, output_path)

    return {
        'output_file': output_path,
        'nodes': nodes_added,
        'links': links_added,
        'total_nodes': sum(nodes_added.values()),
        'total_links': sum(links_added.values()),
        'default_diameter_mm': default_diameter,
        'default_roughness': default_roughness,
        'layers_found': list(set(e.dxf.layer for e in msp if hasattr(e.dxf, 'layer'))),
    }
