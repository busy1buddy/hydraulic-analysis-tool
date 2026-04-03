"""
GIS Shapefile Network Importer
================================
Import water network models from GIS shapefiles.
Requires geopandas, pyproj.

Supports Australian coordinate systems (GDA2020 MGA zones).
"""

import os
import warnings


def import_from_shapefile(pipes_shp, nodes_shp, output_name='gis_network',
                         output_dir=None, source_crs=None, duration_hrs=24):
    """
    Import a water network from GIS shapefiles.

    Parameters
    ----------
    pipes_shp : str
        Path to pipe/line shapefile. Required attributes: id (or PIPE_ID),
        diameter (or DIAMETER_MM), roughness (or C_FACTOR).
        Geometry used for: connectivity (start/end nodes), length.
    nodes_shp : str
        Path to node/point shapefile. Required attributes: id (or NODE_ID),
        type (or NODE_TYPE: junction/reservoir/tank),
        elevation (or ELEVATION_M), demand (or DEMAND_LPS).
    output_name : str
        Name for the output .inp file.
    output_dir : str
        Directory to save the .inp file.
    source_crs : str
        Source coordinate reference system (e.g., 'EPSG:28355' for MGA Zone 55).
        If None, uses the shapefile's CRS. Coordinates are converted to local X,Y.
    duration_hrs : int
        Simulation duration.

    Returns
    -------
    dict with network summary and output path.
    """
    try:
        import geopandas as gpd
    except ImportError:
        return {'error': 'geopandas is required for shapefile import. '
                'Install with: pip install geopandas'}

    import wntr

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'models')
    os.makedirs(output_dir, exist_ok=True)

    # Read shapefiles
    nodes_gdf = gpd.read_file(nodes_shp)
    pipes_gdf = gpd.read_file(pipes_shp)

    # Normalize column names to lowercase
    nodes_gdf.columns = [c.lower() for c in nodes_gdf.columns]
    pipes_gdf.columns = [c.lower() for c in pipes_gdf.columns]

    # Map common column name variations
    node_col_map = {
        'node_id': 'id', 'nodeid': 'id', 'name': 'id',
        'node_type': 'type', 'nodetype': 'type',
        'elevation_m': 'elevation', 'elev': 'elevation',
        'demand_lps': 'demand', 'base_demand': 'demand',
        'head_m': 'head',
    }
    pipe_col_map = {
        'pipe_id': 'id', 'pipeid': 'id', 'name': 'id',
        'diameter_mm': 'diameter', 'dia': 'diameter', 'diam': 'diameter',
        'c_factor': 'roughness', 'hw_c': 'roughness',
        'length_m': 'length', 'len': 'length',
        'start_node': 'start', 'from_node': 'start', 'us_node': 'start',
        'end_node': 'end', 'to_node': 'end', 'ds_node': 'end',
    }

    for old, new in node_col_map.items():
        if old in nodes_gdf.columns and new not in nodes_gdf.columns:
            nodes_gdf = nodes_gdf.rename(columns={old: new})
    for old, new in pipe_col_map.items():
        if old in pipes_gdf.columns and new not in pipes_gdf.columns:
            pipes_gdf = pipes_gdf.rename(columns={old: new})

    # Convert coordinates to local X,Y (metres from centroid)
    if source_crs:
        nodes_gdf = nodes_gdf.to_crs(source_crs)
    centroid_x = nodes_gdf.geometry.x.mean()
    centroid_y = nodes_gdf.geometry.y.mean()

    wn = wntr.network.WaterNetworkModel()
    nodes_added = {'junction': 0, 'reservoir': 0, 'tank': 0}

    # Add nodes
    for _, row in nodes_gdf.iterrows():
        node_id = str(row.get('id', f'N{_}'))
        node_type = str(row.get('type', 'junction')).lower()
        x = float(row.geometry.x - centroid_x)
        y = float(row.geometry.y - centroid_y)

        if node_type == 'reservoir':
            head = float(row.get('head', row.get('elevation', 80)))
            wn.add_reservoir(node_id, base_head=head, coordinates=(x, y))
            nodes_added['reservoir'] += 1
        elif node_type == 'tank':
            elev = float(row.get('elevation', 50))
            wn.add_tank(node_id, elevation=elev, init_level=3,
                       min_level=0.5, max_level=5, diameter=10,
                       coordinates=(x, y))
            nodes_added['tank'] += 1
        else:
            elev = float(row.get('elevation', 0))
            demand = float(row.get('demand', 0)) / 1000
            wn.add_junction(node_id, elevation=elev, base_demand=demand,
                           coordinates=(x, y))
            nodes_added['junction'] += 1

    # Add pipes
    links_added = {'pipe': 0}
    for _, row in pipes_gdf.iterrows():
        pipe_id = str(row.get('id', f'P{_}'))

        # Get start/end from attributes or find nearest nodes
        if 'start' in pipes_gdf.columns and 'end' in pipes_gdf.columns:
            start = str(row['start'])
            end = str(row['end'])
        else:
            # Find nearest nodes to pipe endpoints
            line = row.geometry
            start_pt = line.coords[0]
            end_pt = line.coords[-1]
            start = _find_nearest_node(nodes_gdf, start_pt)
            end = _find_nearest_node(nodes_gdf, end_pt)

        length = float(row.get('length', row.geometry.length))
        diameter = float(row.get('diameter', 200)) / 1000
        roughness = float(row.get('roughness', 130))

        try:
            wn.add_pipe(pipe_id, start, end, length=length,
                       diameter=diameter, roughness=roughness)
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
        'source_crs': source_crs or str(nodes_gdf.crs),
    }


def _find_nearest_node(nodes_gdf, point):
    """Find the nearest node to a coordinate point."""
    from shapely.geometry import Point
    pt = Point(point[0], point[1])
    distances = nodes_gdf.geometry.distance(pt)
    nearest_idx = distances.idxmin()
    return str(nodes_gdf.loc[nearest_idx, 'id'])
