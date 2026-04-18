"""
Terrain Mixin — LiDAR/DEM Sampling for Longitudinal Profiling
============================================================
Handles ingestion of raster or CSV topography data and provides
sampling methods for ground elevation along network coordinates.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

class TerrainMixin:
    def __init__(self):
        self._terrain_data = None  # np.ndarray (grid) or list of points
        self._terrain_bounds = None # (xmin, ymin, xmax, ymax)
        self._terrain_resolution = 1.0 # m/pixel
        self._default_depth_of_cover = 0.75 # m (WSAA standard typical)

    def import_terrain_from_csv(self, path):
        """Import XYZ terrain points from CSV."""
        try:
            data = np.loadtxt(path, delimiter=',', skiprows=1)
            # Assuming Easting, Northing, Elevation
            self._terrain_data = data
            logger.info(f"Imported {len(data)} terrain points.")
            return True
        except Exception as e:
            logger.error(f"Failed to import terrain: {e}")
            return False

    def get_ground_elevation(self, x, y):
        """
        Sample ground elevation at (x, y).
        If no terrain data is loaded, returns node elevation + depth of cover (proxy).
        """
        if self._terrain_data is None:
            # Fallback: if we are at a known node, we return node.elevation + depth
            # But this method doesn't know about nodes.
            # We'll implement interpolation logic here in the future.
            return None

        # Simple nearest neighbor for now
        dists = np.sqrt((self._terrain_data[:, 0] - x)**2 + (self._terrain_data[:, 1] - y)**2)
        idx = np.argmin(dists)
        if dists[idx] < 50.0: # 50m search radius
            return self._terrain_data[idx, 2]
        return None

    def get_path_hgl(self, path_labels, steady_results):
        """Extract HGL (Pressure + Elevation) for a sequence of nodes."""
        if not steady_results:
            return None
        
        pressures = steady_results.get('pressures', {})
        hgl = []
        for nid in path_labels:
            try:
                node = self.wn.get_node(nid)
                p_data = pressures.get(nid, {})
                p = p_data.get('avg_m', 0.0)
                hgl.append(p + node.elevation)
            except Exception:
                hgl.append(0.0)
        return hgl

    def get_path_profile_with_terrain(self, start_node, end_node, steady_results=None):
        """
        Extract profile including ground surface, HGL, and appurtenances.
        """
        profile = self.get_path_profile(start_node, end_node)
        if not profile:
            return None

        # Add ground elevation
        ground_elev = []
        for i, nid in enumerate(profile['labels']):
            node = self.wn.get_node(nid)
            x, y = node.coordinates
            ge = self.get_ground_elevation(x, y)
            if ge is None:
                # If no LiDAR, assume ground is 0.75m above pipe
                # For nodes, pipe elevation = node elevation
                ge = node.elevation + self._default_depth_of_cover
            ground_elev.append(ge)
            
        profile['ground_elevation'] = ground_elev
        
        # Add HGL
        if steady_results:
            profile['hgl'] = self.get_path_hgl(profile['labels'], steady_results)
        
        # Identify Appurtenances (Pumps/Valves)
        appurtenances = []
        path_nodes = profile['labels']
        for i in range(len(path_nodes)-1):
            n1 = path_nodes[i]
            n2 = path_nodes[i+1]
            
            # Find the link between these two nodes on the path
            for link_name in self.wn.get_links_for_node(n1):
                link = self.wn.get_link(link_name)
                if link.start_node_name == n2 or link.end_node_name == n2:
                    if link.link_type in ['Pump', 'Valve']:
                        appurtenances.append({
                            'chainage': profile['chainage'][i],
                            'elevation': profile['elevation'][i],
                            'label': f"{link.link_type}: {link_name}"
                        })
                    break
                    
        profile['appurtenances'] = appurtenances
        
        # Suggest Air Valves
        profile['suggested_avs'] = self.suggest_air_valves(profile)
        
        # Suggest Scour Valves
        profile['suggested_scours'] = self.suggest_scour_valves(profile)
        
        # Detect Vacuum Zones
        profile['vacuum_zones'] = self.detect_vacuum_zones(profile)
        
        # Detect Cavitation Risk (Pressure < -8.0m gauge)
        profile['cavitation_risk'] = self.detect_cavitation_risk(profile)
        
        return profile

    def suggest_scour_valves(self, profile):
        """
        Identify topographical valleys (local minima) along the path.
        """
        elev = profile['elevation']
        chainage = profile['chainage']
        
        suggestions = []
        if len(elev) < 3:
            return suggestions
            
        for i in range(1, len(elev)-1):
            if elev[i] < elev[i-1] and elev[i] <= elev[i+1]:
                suggestions.append({
                    'chainage': chainage[i],
                    'elevation': elev[i],
                    'label': "Suggested Scour Valve (Low Point)"
                })
        return suggestions

    def suggest_air_valves(self, profile):
        """
        Identify topographical peaks (local maxima) along the path.
        """
        elev = profile['elevation']
        chainage = profile['chainage']
        
        suggestions = []
        if len(elev) < 3:
            return suggestions
            
        for i in range(1, len(elev)-1):
            if elev[i] > elev[i-1] and elev[i] >= elev[i+1]:
                # Find pipe diameter at this location
                try:
                    p1 = self.wn.get_node(profile['labels'][i])
                    # Get connected pipe diameter
                    connected_links = self.wn.get_links_for_node(profile['labels'][i])
                    pipe_dn_mm = 100 # default
                    if connected_links:
                        link = self.wn.get_link(connected_links[0])
                        if hasattr(link, 'diameter'):
                            pipe_dn_mm = link.diameter * 1000
                            
                    # Simple Sizing Logic (WSAA)
                    # Target air velocity < 30 m/s during 1.0 m/s water fill
                    # Q_water = V_water * A_pipe = 1.0 * pi/4 * D_pipe^2
                    # Q_air_required = Q_water
                    # A_av = Q_air / V_air_target = Q_water / 30
                    # D_av = sqrt(4 * A_av / pi)
                    # Simplified: D_av = D_pipe / sqrt(30) ~= D_pipe / 5.5
                    av_size_mm = pipe_dn_mm / 5.5
                    # Round to standard sizes (25, 50, 80, 100, 150)
                    standards = [25, 50, 80, 100, 150, 200, 250, 300]
                    recommended = 50
                    for s in standards:
                        if s >= av_size_mm:
                            recommended = s
                            break
                    
                    suggestions.append({
                        'chainage': chainage[i],
                        'elevation': elev[i],
                        'label': f"Suggested Air Valve (DN{recommended} Orifice)",
                        'pipe_dn': pipe_dn_mm,
                        'av_dn': recommended
                    })
                except Exception:
                    suggestions.append({
                        'chainage': chainage[i],
                        'elevation': elev[i],
                        'label': "Suggested Air Valve"
                    })
        return suggestions

    def detect_cavitation_risk(self, profile, limit_m=-8.0):
        """
        Identify segments where Pressure < limit_m.
        Pressure = HGL - Pipe Elevation.
        """
        if 'hgl' not in profile:
            return []
            
        hgl = profile['hgl']
        elev = profile['elevation']
        chainage = profile['chainage']
        
        risks = []
        in_risk = False
        start_c = 0
        
        for i in range(len(hgl)):
            pressure = hgl[i] - elev[i]
            if pressure < limit_m:
                if not in_risk:
                    in_risk = True
                    start_c = chainage[i]
            else:
                if in_risk:
                    in_risk = False
                    risks.append((start_c, chainage[i]))
                    
        if in_risk:
            risks.append((start_c, chainage[-1]))
            
        return risks

    def detect_vacuum_zones(self, profile):
        """
        Identify segments where HGL < Pipe Elevation.
        Returns list of (chainage_start, chainage_end).
        """
        if 'hgl' not in profile:
            return []
            
        hgl = profile['hgl']
        elev = profile['elevation']
        chainage = profile['chainage']
        
        zones = []
        in_vacuum = False
        start_c = 0
        
        for i in range(len(hgl)):
            # Buffer of 0.1m to avoid numerical noise
            if hgl[i] < elev[i] - 0.1:
                if not in_vacuum:
                    in_vacuum = True
                    start_c = chainage[i]
            else:
                if in_vacuum:
                    in_vacuum = False
                    zones.append((start_c, chainage[i]))
                    
        if in_vacuum:
            zones.append((start_c, chainage[-1]))
            
        return zones
