"""
Topography Ingestion
==================
Map LiDAR/DEM elevation data to hydraulic network nodes.
"""

import os
import warnings
import wntr

def apply_elevations_from_dem(inp_file, dem_file, output_inp_file=None):
    """
    Drape a network over a DEM to extract node elevations.
    
    Parameters
    ----------
    inp_file : str
        Path to the EPANET .inp file.
    dem_file : str
        Path to the Digital Elevation Model (e.g., .tif, .asc).
    output_inp_file : str, optional
        Path for the updated .inp file. If None, overwrites inp_file.
        
    Returns
    -------
    dict
        Summary of the elevation mapping process.
    """
    try:
        import rasterio
    except ImportError:
        return {'error': 'rasterio is required for DEM import. Install with: pip install rasterio'}
    
    # Load the water network model
    wn = wntr.network.WaterNetworkModel(inp_file)
    
    nodes_updated = 0
    nodes_out_of_bounds = 0
    
    with rasterio.open(dem_file) as src:
        for name, node in wn.nodes():
            if hasattr(node, 'coordinates') and node.coordinates:
                x, y = node.coordinates
                
                # Convert spatial coordinates to raster row/col
                try:
                    row, col = src.index(x, y)
                    
                    # Read the pixel value
                    # We use windowed reading to avoid loading massive DEMs into memory
                    window = rasterio.windows.Window(col, row, 1, 1)
                    elevation_data = src.read(1, window=window)
                    
                    if elevation_data.size > 0:
                        elevation = float(elevation_data[0, 0])
                        
                        # Handle nodata values gracefully
                        if src.nodata is not None and elevation == src.nodata:
                            nodes_out_of_bounds += 1
                        else:
                            node.elevation = elevation
                            nodes_updated += 1
                    else:
                        nodes_out_of_bounds += 1
                except (IndexError, ValueError):
                    # Node is outside the DEM boundary
                    nodes_out_of_bounds += 1
                    
    if output_inp_file is None:
        output_inp_file = inp_file
        
    # Write the updated network back to an INP file
    wntr.network.write_inpfile(wn, output_inp_file)
    
    return {
        'status': 'success',
        'nodes_updated': nodes_updated,
        'nodes_out_of_bounds': nodes_out_of_bounds,
        'output_file': output_inp_file
    }
