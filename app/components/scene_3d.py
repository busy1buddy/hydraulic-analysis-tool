"""
3D Network Visualization Engine (Enhanced)
============================================
Renders water/mining pipe networks in interactive 3D using Three.js
via NiceGUI's ui.scene(). Features:
- 3D pipe rendering with diameter-proportional thickness
- Color-coded results overlay (pressure, velocity, flow)
- Node markers (junctions, reservoirs, tanks, pumps)
- Click-to-select elements with glow highlighting
- Elevation-based 3D layout
- Animated flow particles showing direction and velocity
- Material-based pipe textures/colors
- EPS result animation with play/pause/step
- Measurement tool (click two points for distance)
- Toggleable labels (names, diameters, flow values, pressures)
- Screenshot export
"""

import math
import json
import numpy as np
from nicegui import ui
from app.theme import COLORS


# ── Material colors for different pipe materials ──
MATERIAL_COLORS = {
    'default': '#4488cc',
    'ductile_iron': '#808080',
    'di': '#808080',
    'pvc': '#4488ff',
    'pe': '#1a1a2e',
    'hdpe': '#1a1a2e',
    'concrete': '#b0a090',
    'steel': '#707880',
    'copper': '#b87333',
    'cast_iron': '#555555',
}

# Material visual styles: (primary_color, stripe_color, opacity)
MATERIAL_STYLES = {
    'default':      ('#4488cc', None, 0.85),
    'ductile_iron': ('#808080', '#606060', 0.90),
    'di':           ('#808080', '#606060', 0.90),
    'pvc':          ('#4488ff', '#2266dd', 0.80),
    'pe':           ('#1a1a2e', '#333355', 0.85),
    'hdpe':         ('#1a1a2e', '#333355', 0.85),
    'concrete':     ('#b0a090', '#8a7a6a', 0.95),
    'steel':        ('#707880', '#505860', 0.90),
    'copper':       ('#b87333', '#996030', 0.90),
    'cast_iron':    ('#555555', '#444444', 0.90),
}

# Result color scales
PRESSURE_COLORS = [
    (0, '#ef4444'),     # Low pressure - red
    (10, '#f97316'),    # Below minimum - orange
    (20, '#f59e0b'),    # At minimum - yellow
    (30, '#10b981'),    # Good - green
    (40, '#06b6d4'),    # High - cyan
    (60, '#3b82f6'),    # Very high - blue
]

VELOCITY_COLORS = [
    (0, '#3b82f6'),     # Low - blue
    (0.5, '#06b6d4'),   # Moderate - cyan
    (1.0, '#10b981'),   # Good - green
    (1.5, '#f59e0b'),   # High - yellow
    (2.0, '#ef4444'),   # Exceeds limit - red
]


def _interpolate_color(value, color_scale):
    """Interpolate color from a scale based on value."""
    if value <= color_scale[0][0]:
        return color_scale[0][1]
    if value >= color_scale[-1][0]:
        return color_scale[-1][1]

    for i in range(len(color_scale) - 1):
        v0, c0 = color_scale[i]
        v1, c1 = color_scale[i + 1]
        if v0 <= value <= v1:
            t = (value - v0) / (v1 - v0) if v1 != v0 else 0
            r0, g0, b0 = int(c0[1:3], 16), int(c0[3:5], 16), int(c0[5:7], 16)
            r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
            r = int(r0 + t * (r1 - r0))
            g = int(g0 + t * (g1 - g0))
            b = int(b0 + t * (b1 - b0))
            return f'#{r:02x}{g:02x}{b:02x}'
    return color_scale[-1][1]


def _get_node_coords_3d(wn, scale_z=1.0):
    """Extract 3D coordinates for all nodes. Uses elevation as Z."""
    coords = {}
    for name in list(wn.junction_name_list) + list(wn.reservoir_name_list) + list(wn.tank_name_list):
        node = wn.get_node(name)
        x, y = node.coordinates
        if hasattr(node, 'elevation'):
            z = node.elevation * scale_z
        elif hasattr(node, 'base_head'):
            z = node.base_head * scale_z
        else:
            z = 0
        coords[name] = (x, y, z)
    return coords


def _detect_pipe_material(pipe):
    """Detect pipe material from roughness or name heuristics."""
    roughness = pipe.roughness
    name_lower = pipe.name.lower() if pipe.name else ''

    # Check name hints first
    for mat in ['pvc', 'pe', 'hdpe', 'steel', 'concrete', 'copper', 'di']:
        if mat in name_lower:
            return mat

    # Infer from Hazen-Williams C-factor ranges
    if roughness >= 140:
        return 'pvc'       # Smooth plastic
    elif roughness >= 120:
        return 'pe'        # PE/HDPE
    elif roughness >= 100:
        return 'ductile_iron'  # DI
    elif roughness >= 80:
        return 'concrete'
    elif roughness >= 60:
        return 'steel'
    else:
        return 'cast_iron'


class NetworkScene3D:
    """Manages a 3D scene for network visualization with full enhancement suite."""

    def __init__(self, scene, wn, scale_z=0.5, pipe_scale=0.3):
        """
        Parameters
        ----------
        scene : ui.scene context
            NiceGUI 3D scene context.
        wn : wntr.network.WaterNetworkModel
            The network to render.
        scale_z : float
            Vertical exaggeration factor for elevation.
        pipe_scale : float
            Scale factor for pipe diameters in 3D.
        """
        self.scene = scene
        self.wn = wn
        self.scale_z = scale_z
        self.pipe_scale = pipe_scale
        self.coords = _get_node_coords_3d(wn, scale_z)
        self.objects = {}           # element_id -> 3D object
        self.result_data = None

        # Compute network extent for proportional sizing
        if self.coords:
            xs = [c[0] for c in self.coords.values()]
            ys = [c[1] for c in self.coords.values()]
            self._extent = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
        else:
            self._extent = 100.0

        # Scale factors derived from extent (target: nodes ~1-2% of extent)
        self._node_radius = self._extent * 0.012
        self._reservoir_size = self._extent * 0.025
        self._tank_radius = self._extent * 0.018
        self._tank_height = self._extent * 0.04
        self._pump_radius = self._extent * 0.015
        self._pump_height = self._extent * 0.03
        self._valve_size = self._extent * 0.02
        self._label_offset = self._extent * 0.02
        self._font_size = max(1.0, self._extent * 0.025)

        # Enhancement state
        self.particle_objects = []  # list of particle sphere objects
        self.pipe_flow_data = {}    # pipe_name -> {start, end, velocity, direction}
        self.label_objects = {}     # label category -> list of 3D text objects
        self.selected_element = None
        self.selection_highlight = None
        self.measurement_points = []
        self.measurement_objects = []
        self.labels_visible = {
            'names': True,
            'diameters': False,
            'flows': False,
            'pressures': False,
        }

    # ── Core rendering ──────────────────────────────────────────

    def render_network(self, color_by=None, results=None, show_material_colors=False):
        """Render the full network in 3D.

        Parameters
        ----------
        color_by : str or None
            'pressure', 'velocity', 'flow', or None for default colors.
        results : dict or None
            Analysis results for coloring.
        show_material_colors : bool
            If True, color pipes by detected material instead of uniform color.
        """
        self.result_data = results
        self.label_objects = {'names': [], 'diameters': [], 'flows': [], 'pressures': []}

        # Render pipes
        for pipe_name in self.wn.pipe_name_list:
            self._render_pipe(pipe_name, color_by, results, show_material_colors)

        # Render valves
        for valve_name in self.wn.valve_name_list:
            self._render_valve(valve_name)

        # Render nodes
        for name in self.wn.junction_name_list:
            self._render_junction(name, color_by, results)

        for name in self.wn.reservoir_name_list:
            self._render_reservoir(name)

        for name in self.wn.tank_name_list:
            self._render_tank(name)

        # Render pumps
        for name in self.wn.pump_name_list:
            self._render_pump(name)

        # Apply initial label visibility
        self._apply_label_visibility()

    def _pipe_radius(self, pipe):
        """Calculate visual pipe radius proportional to network extent."""
        dia_mm = pipe.diameter * 1000
        min_r = self._extent * 0.002
        max_r = self._extent * 0.008
        # Linear map: 100mm -> min_r, 600mm -> max_r
        t = max(0, min(1, (dia_mm - 100) / 500))
        return min_r + t * (max_r - min_r)

    def _render_pipe(self, name, color_by=None, results=None, show_material=False):
        """Render a pipe as a cylinder between two nodes."""
        pipe = self.wn.get_link(name)
        sn, en = pipe.start_node_name, pipe.end_node_name

        if sn not in self.coords or en not in self.coords:
            return

        x1, y1, z1 = self.coords[sn]
        x2, y2, z2 = self.coords[en]

        dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
        length = math.sqrt(dx**2 + dy**2 + dz**2)
        if length < 0.01:
            return

        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        mid_z = (z1 + z2) / 2

        radius = self._pipe_radius(pipe)

        # Determine color
        material_type = _detect_pipe_material(pipe)
        opacity = 0.85

        if color_by == 'velocity' and results and 'flows' in results:
            if name in results['flows']:
                vel = results['flows'][name].get('avg_velocity_ms', 0)
                color = _interpolate_color(vel, VELOCITY_COLORS)
            else:
                color = MATERIAL_COLORS.get(material_type, MATERIAL_COLORS['default'])
        elif color_by == 'pressure' and results and 'pressures' in results:
            p_vals = []
            for node_name in [sn, en]:
                if node_name in results['pressures']:
                    p_vals.append(results['pressures'][node_name].get('avg_m', 30))
            if p_vals:
                color = _interpolate_color(sum(p_vals) / len(p_vals), PRESSURE_COLORS)
            else:
                color = MATERIAL_COLORS['default']
        elif color_by == 'flow' and results and 'flows' in results:
            if name in results['flows']:
                flow = abs(results['flows'][name].get('avg_lps', 0))
                color = _interpolate_color(flow / 5, PRESSURE_COLORS)
            else:
                color = MATERIAL_COLORS['default']
        elif show_material:
            style = MATERIAL_STYLES.get(material_type, MATERIAL_STYLES['default'])
            color, _, opacity = style
        else:
            color = MATERIAL_COLORS['default']

        # Rotation to align Y-axis cylinder between two scene-space points
        # Scene mapping: WNTR (x,y,z) -> scene (x, z, -y)
        # So scene direction = (dx, dz, -dy) where dx/dy/dz are in coords space
        sx, sy, sz = dx, dz, -dy  # scene-space direction
        h = math.sqrt(sx**2 + sy**2)
        rx = math.asin(max(-1.0, min(1.0, sz / length))) if length > 0 else 0
        rz = math.atan2(-sx, sy) if h > 0.001 else 0

        with self.scene:
            obj = self.scene.cylinder(radius, radius, length).move(
                mid_x, mid_z, -mid_y  # Three.js: Y is up
            ).rotate(rx, 0, rz).material(color, opacity=opacity).with_name(name)
            self.objects[name] = obj

            # Material stripe ring for textured mode
            if show_material:
                stripe = MATERIAL_STYLES.get(material_type, MATERIAL_STYLES['default'])[1]
                if stripe:
                    self.scene.cylinder(radius * 1.15, radius * 1.15, length * 0.04).move(
                        mid_x, mid_z, -mid_y
                    ).rotate(rx, 0, rz).material(stripe, opacity=0.95)

        # Store flow data for particle animation
        flow_val = 0
        vel_val = 0
        if results and 'flows' in results and name in results['flows']:
            flow_val = results['flows'][name].get('avg_lps', 0)
            vel_val = results['flows'][name].get('avg_velocity_ms', 0)

        self.pipe_flow_data[name] = {
            'start': (x1, y1, z1),
            'end': (x2, y2, z2),
            'flow_lps': flow_val,
            'velocity': vel_val,
            'length': length,
            'direction': 1 if flow_val >= 0 else -1,
        }

        # Diameter label (hidden by default)
        dia_mm = pipe.diameter * 1000
        lbl_offset = self._label_offset
        fs = f'font-size: {self._font_size * 0.7:.1f}px'
        with self.scene:
            dia_label = self.scene.text3d(
                f'DN{dia_mm:.0f}', style=fs
            ).move(mid_x, mid_z + radius + lbl_offset, -mid_y).visible(False)
            self.label_objects['diameters'].append(dia_label)

        # Flow label (hidden by default)
        if flow_val != 0:
            with self.scene:
                flow_label = self.scene.text3d(
                    f'{abs(flow_val):.1f} L/s', style=fs
                ).move(mid_x, mid_z + radius + lbl_offset * 2, -mid_y).visible(False)
                self.label_objects['flows'].append(flow_label)

    def _render_valve(self, name):
        """Render a valve as a small orange box."""
        valve = self.wn.get_link(name)
        sn, en = valve.start_node_name, valve.end_node_name

        if sn not in self.coords or en not in self.coords:
            return

        x1, y1, z1 = self.coords[sn]
        x2, y2, z2 = self.coords[en]
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        mid_z = (z1 + z2) / 2

        s = self._valve_size
        with self.scene:
            obj = self.scene.box(s, s, s).move(
                mid_x, mid_z, -mid_y
            ).material(COLORS['orange']).with_name(name)
            self.objects[name] = obj

    def _render_junction(self, name, color_by=None, results=None):
        """Render a junction as a sphere."""
        if name not in self.coords:
            return

        x, y, z = self.coords[name]
        r = self._node_radius

        color = COLORS['green']
        pressure_val = None
        if color_by == 'pressure' and results and 'pressures' in results:
            if name in results['pressures']:
                pressure_val = results['pressures'][name].get('min_m', 30)
                color = _interpolate_color(pressure_val, PRESSURE_COLORS)

        fs = f'font-size: {self._font_size:.1f}px'
        fs_sm = f'font-size: {self._font_size * 0.8:.1f}px'
        lbl_off = self._label_offset

        with self.scene:
            obj = self.scene.sphere(r).move(x, z, -y).material(color).with_name(name)
            self.objects[name] = obj

            # Name label (visible by default)
            name_label = self.scene.text3d(name, style=fs).move(
                x, z + r + lbl_off, -y)
            self.label_objects['names'].append(name_label)

            # Pressure label (hidden by default)
            if pressure_val is not None:
                p_label = self.scene.text3d(
                    f'{pressure_val:.1f}m', style=fs_sm
                ).move(x, z + r + lbl_off * 2.5, -y).visible(False)
                self.label_objects['pressures'].append(p_label)

    def _render_reservoir(self, name):
        """Render a reservoir as a blue cube."""
        if name not in self.coords:
            return
        x, y, z = self.coords[name]
        s = self._reservoir_size
        fs = f'font-size: {self._font_size:.1f}px'

        with self.scene:
            obj = self.scene.box(s, s, s).move(x, z, -y).material(
                COLORS['accent'], opacity=0.8).with_name(name)
            self.objects[name] = obj
            name_label = self.scene.text3d(name, style=fs).move(
                x, z + s / 2 + self._label_offset, -y)
            self.label_objects['names'].append(name_label)

    def _render_tank(self, name):
        """Render a tank as a cyan cylinder."""
        if name not in self.coords:
            return
        x, y, z = self.coords[name]
        r = self._tank_radius
        h = self._tank_height
        fs = f'font-size: {self._font_size:.1f}px'

        with self.scene:
            obj = self.scene.cylinder(r, r, h).move(x, z, -y).material(
                COLORS['cyan'], opacity=0.7).with_name(name)
            self.objects[name] = obj
            name_label = self.scene.text3d(name, style=fs).move(
                x, z + h / 2 + self._label_offset, -y)
            self.label_objects['names'].append(name_label)

    def _render_pump(self, name):
        """Render a pump as a green cone/triangle."""
        pump = self.wn.get_link(name)
        sn, en = pump.start_node_name, pump.end_node_name

        if sn not in self.coords or en not in self.coords:
            return

        x1, y1, z1 = self.coords[sn]
        x2, y2, z2 = self.coords[en]
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        mid_z = (z1 + z2) / 2
        r = self._pump_radius
        h = self._pump_height
        fs = f'font-size: {self._font_size:.1f}px'

        with self.scene:
            obj = self.scene.cylinder(0, r, h).move(
                mid_x, mid_z, -mid_y
            ).material('#22c55e').with_name(name)
            self.objects[name] = obj
            name_label = self.scene.text3d(name, style=fs).move(
                mid_x, mid_z + h / 2 + self._label_offset, -mid_y)
            self.label_objects['names'].append(name_label)

    # ── 1. Flow Particle Animation ──────────────────────────────

    def create_particles(self, particles_per_pipe=3):
        """Create flow particles along each pipe for animation.

        Returns the particle data structure needed by the animation timer.
        Particles are small spheres positioned along each pipe path.
        """
        self.clear_particles()
        particle_data = []

        for pipe_name, pdata in self.pipe_flow_data.items():
            vel = abs(pdata.get('velocity', 0))
            if vel < 0.01:
                continue  # Skip zero-flow pipes

            x1, y1, z1 = pdata['start']
            x2, y2, z2 = pdata['end']
            direction = pdata['direction']
            pipe_len = pdata['length']

            # More particles for longer pipes, fewer for short ones
            n_particles = max(1, min(particles_per_pipe, int(pipe_len / 5)))

            for i in range(n_particles):
                t = (i + 0.5) / n_particles  # Spread evenly along pipe
                px = x1 + t * (x2 - x1)
                py = y1 + t * (y2 - y1)
                pz = z1 + t * (z2 - z1)

                # Particle color: brighter = faster
                brightness = min(1.0, vel / 2.0)
                r = int(100 + 155 * brightness)
                g = int(200 + 55 * brightness)
                b = 255
                p_color = f'#{r:02x}{g:02x}{b:02x}'

                with self.scene:
                    p_radius = self._node_radius * (0.6 + min(vel, 2) * 0.3)
                    particle = self.scene.sphere(p_radius).move(
                        px, pz, -py  # Three.js Y-up
                    ).material(p_color, opacity=0.9)

                self.particle_objects.append(particle)
                particle_data.append({
                    'obj': particle,
                    'pipe': pipe_name,
                    'start': (x1, y1, z1),
                    'end': (x2, y2, z2),
                    't': t,
                    'speed': vel / max(pipe_len, 1) * direction,
                    'direction': direction,
                })

        return particle_data

    def animate_particles(self, particle_data, dt=0.05):
        """Advance particles one step along their pipes.

        Call this repeatedly from a ui.timer to animate.
        dt controls step size (fraction of pipe length per tick).
        """
        for p in particle_data:
            p['t'] += p['speed'] * dt
            # Wrap around
            if p['t'] > 1.0:
                p['t'] -= 1.0
            elif p['t'] < 0.0:
                p['t'] += 1.0

            x1, y1, z1 = p['start']
            x2, y2, z2 = p['end']
            t = p['t']
            px = x1 + t * (x2 - x1)
            py = y1 + t * (y2 - y1)
            pz = z1 + t * (z2 - z1)
            p['obj'].move(px, pz, -py)

    def clear_particles(self):
        """Remove all particle objects from the scene."""
        for p in self.particle_objects:
            try:
                p.delete()
            except Exception:
                pass
        self.particle_objects = []

    # ── 4. Selection Highlighting ───────────────────────────────

    def highlight_element(self, element_name):
        """Add a glow/outline highlight to the selected element.

        Creates a slightly larger, semi-transparent wireframe around the element.
        """
        self.clear_highlight()
        self.selected_element = element_name

        if element_name is None:
            return

        # Determine element position and type, use proportional highlight sizes
        glow_scale = 1.8  # Highlight is 1.8x the element size

        if element_name in self.wn.junction_name_list:
            if element_name not in self.coords:
                return
            x, y, z = self.coords[element_name]
            with self.scene:
                self.selection_highlight = self.scene.sphere(
                    self._node_radius * glow_scale
                ).move(x, z, -y).material('#ffff00', opacity=0.25)

        elif element_name in self.wn.reservoir_name_list:
            if element_name not in self.coords:
                return
            x, y, z = self.coords[element_name]
            s = self._reservoir_size * glow_scale
            with self.scene:
                self.selection_highlight = self.scene.box(s, s, s).move(
                    x, z, -y
                ).material('#ffff00', opacity=0.25)

        elif element_name in self.wn.tank_name_list:
            if element_name not in self.coords:
                return
            x, y, z = self.coords[element_name]
            with self.scene:
                self.selection_highlight = self.scene.cylinder(
                    self._tank_radius * glow_scale,
                    self._tank_radius * glow_scale,
                    self._tank_height * glow_scale
                ).move(x, z, -y).material('#ffff00', opacity=0.25)

        elif element_name in self.wn.pipe_name_list:
            pipe = self.wn.get_link(element_name)
            sn, en = pipe.start_node_name, pipe.end_node_name
            if sn not in self.coords or en not in self.coords:
                return
            x1, y1, z1 = self.coords[sn]
            x2, y2, z2 = self.coords[en]
            dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
            length = math.sqrt(dx**2 + dy**2 + dz**2)
            if length < 0.01:
                return
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            mid_z = (z1 + z2) / 2
            radius = self._pipe_radius(pipe)
            sx, sy, sz = dx, dz, -dy
            h = math.sqrt(sx**2 + sy**2)
            rx = math.asin(max(-1.0, min(1.0, sz / length))) if length > 0 else 0
            rz = math.atan2(-sx, sy) if h > 0.001 else 0

            with self.scene:
                self.selection_highlight = self.scene.cylinder(
                    radius * 2.5, radius * 2.5, length * 1.01
                ).move(mid_x, mid_z, -mid_y).rotate(rx, 0, rz).material(
                    '#ffff00', opacity=0.2)

        elif element_name in self.wn.pump_name_list:
            pump = self.wn.get_link(element_name)
            sn, en = pump.start_node_name, pump.end_node_name
            if sn not in self.coords or en not in self.coords:
                return
            x1, y1, z1 = self.coords[sn]
            x2, y2, z2 = self.coords[en]
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            mid_z = (z1 + z2) / 2
            with self.scene:
                self.selection_highlight = self.scene.sphere(
                    self._pump_radius * glow_scale
                ).move(mid_x, mid_z, -mid_y).material('#ffff00', opacity=0.25)

        elif element_name in self.wn.valve_name_list:
            valve = self.wn.get_link(element_name)
            sn, en = valve.start_node_name, valve.end_node_name
            if sn not in self.coords or en not in self.coords:
                return
            x1, y1, z1 = self.coords[sn]
            x2, y2, z2 = self.coords[en]
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            mid_z = (z1 + z2) / 2
            s = self._valve_size * glow_scale
            with self.scene:
                self.selection_highlight = self.scene.box(s, s, s).move(
                    mid_x, mid_z, -mid_y
                ).material('#ffff00', opacity=0.25)

    def clear_highlight(self):
        """Remove the current selection highlight."""
        if self.selection_highlight is not None:
            try:
                self.selection_highlight.delete()
            except Exception:
                pass
            self.selection_highlight = None
        self.selected_element = None

    # ── 5. Measurement Tool ─────────────────────────────────────

    def add_measurement_point(self, x, y, z):
        """Add a measurement point (in scene coordinates: x, y_up, z).

        When two points are placed, draws a line and returns the distance.
        Returns (distance_3d, distance_horiz) or None if < 2 points.
        """
        self.measurement_points.append((x, y, z))

        # Draw marker at point
        with self.scene:
            marker = self.scene.sphere(self._node_radius * 0.8).move(x, y, z).material('#ff00ff', opacity=0.9)
            self.measurement_objects.append(marker)

        if len(self.measurement_points) >= 2:
            p1 = self.measurement_points[-2]
            p2 = self.measurement_points[-1]

            # Draw line between points
            with self.scene:
                line = self.scene.line(
                    [p1[0], p1[1], p1[2]],
                    [p2[0], p2[1], p2[2]],
                ).material('#ff00ff')
                self.measurement_objects.append(line)

            # Calculate distances
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]  # vertical in Three.js
            dz = p2[2] - p1[2]
            dist_3d = math.sqrt(dx**2 + dy**2 + dz**2)
            dist_horiz = math.sqrt(dx**2 + dz**2)
            dist_vert = abs(dy)

            # Draw distance label at midpoint
            mx = (p1[0] + p2[0]) / 2
            my = (p1[1] + p2[1]) / 2 + self._label_offset * 2
            mz = (p1[2] + p2[2]) / 2
            with self.scene:
                label = self.scene.text3d(
                    f'{dist_3d:.1f}m', style=f'font-size: {self._font_size:.1f}px'
                ).move(mx, my, mz)
                self.measurement_objects.append(label)

            # Reset for next measurement pair
            self.measurement_points = []

            return {
                'distance_3d': round(dist_3d, 2),
                'distance_horizontal': round(dist_horiz, 2),
                'distance_vertical': round(dist_vert, 2),
            }
        return None

    def clear_measurements(self):
        """Remove all measurement markers and lines."""
        for obj in self.measurement_objects:
            try:
                obj.delete()
            except Exception:
                pass
        self.measurement_objects = []
        self.measurement_points = []

    # ── 6. Labels Toggle ────────────────────────────────────────

    def set_labels_visible(self, category, visible):
        """Toggle visibility of a label category.

        Parameters
        ----------
        category : str
            'names', 'diameters', 'flows', or 'pressures'
        visible : bool
        """
        self.labels_visible[category] = visible
        for label_obj in self.label_objects.get(category, []):
            try:
                label_obj.visible(visible)
            except Exception:
                pass

    def _apply_label_visibility(self):
        """Apply current label visibility state to all labels."""
        for category, visible in self.labels_visible.items():
            for label_obj in self.label_objects.get(category, []):
                try:
                    label_obj.visible(visible)
                except Exception:
                    pass

    # ── 3. EPS Result Animation ─────────────────────────────────

    def update_colors_for_timestep(self, results_at_t, color_by='pressure'):
        """Update pipe and node colors for a specific timestep.

        Parameters
        ----------
        results_at_t : dict
            Dict with 'pressures' and 'flows' for a single timestep.
            Format: {node_name: pressure_value} or {pipe_name: velocity_value}
        color_by : str
            'pressure' or 'velocity'
        """
        if color_by == 'pressure':
            for name, obj in self.objects.items():
                if name in self.wn.junction_name_list:
                    p = results_at_t.get('pressures', {}).get(name, 30)
                    color = _interpolate_color(p, PRESSURE_COLORS)
                    try:
                        obj.material(color)
                    except Exception:
                        pass
                elif name in self.wn.pipe_name_list:
                    pipe = self.wn.get_link(name)
                    sn, en = pipe.start_node_name, pipe.end_node_name
                    p_vals = []
                    for nn in [sn, en]:
                        if nn in results_at_t.get('pressures', {}):
                            p_vals.append(results_at_t['pressures'][nn])
                    if p_vals:
                        color = _interpolate_color(sum(p_vals) / len(p_vals), PRESSURE_COLORS)
                        try:
                            obj.material(color, opacity=0.85)
                        except Exception:
                            pass

        elif color_by == 'velocity':
            for name, obj in self.objects.items():
                if name in self.wn.pipe_name_list:
                    vel = results_at_t.get('velocities', {}).get(name, 0)
                    color = _interpolate_color(vel, VELOCITY_COLORS)
                    try:
                        obj.material(color, opacity=0.85)
                    except Exception:
                        pass

    # ── Camera ──────────────────────────────────────────────────

    def center_camera(self):
        """Move camera to center on the network."""
        if not self.coords:
            return
        xs = [c[0] for c in self.coords.values()]
        ys = [c[1] for c in self.coords.values()]
        zs = [c[2] for c in self.coords.values()]

        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        cz = (min(zs) + max(zs)) / 2

        span = max(max(xs) - min(xs), max(ys) - min(ys), 20)

        self.scene.move_camera(
            x=cx, y=cz + span, z=-cy + span * 0.7,
            look_at_x=cx, look_at_y=cz, look_at_z=-cy,
        )

    # ── 7. Screenshot Export ────────────────────────────────────

    def get_screenshot_js(self, scene_id):
        """Return JavaScript code to capture the 3D canvas as a PNG download.

        Parameters
        ----------
        scene_id : str
            The HTML element ID of the NiceGUI scene container.
        """
        return f"""
        (() => {{
            const container = document.getElementById('{scene_id}');
            if (!container) {{
                // Try finding the canvas inside nicegui scene elements
                const canvases = document.querySelectorAll('canvas');
                if (canvases.length === 0) return;
                const canvas = canvases[canvases.length - 1];
                const url = canvas.toDataURL('image/png');
                const a = document.createElement('a');
                a.href = url;
                a.download = 'network_3d_view.png';
                a.click();
                return;
            }}
            const canvas = container.querySelector('canvas');
            if (!canvas) return;
            const url = canvas.toDataURL('image/png');
            const a = document.createElement('a');
            a.href = url;
            a.download = 'network_3d_view.png';
            a.click();
        }})();
        """


class EPSAnimator:
    """Manages stepping through Extended Period Simulation timesteps.

    Extracts per-timestep pressure and velocity data from WNTR simulation
    results and provides play/pause/step controls for 3D animation.
    """

    def __init__(self, wn, steady_results_obj):
        """
        Parameters
        ----------
        wn : wntr.network.WaterNetworkModel
        steady_results_obj : wntr SimulationResults
            The raw WNTR simulation results object (not the dict).
        """
        self.wn = wn
        self.raw_results = steady_results_obj
        self.timesteps = []
        self.current_step = 0
        self._extract_timesteps()

    def _extract_timesteps(self):
        """Extract per-timestep data from the WNTR results."""
        pressures_df = self.raw_results.node['pressure']
        flows_df = self.raw_results.link['flowrate']

        for t_idx, t_val in enumerate(pressures_df.index):
            step_data = {
                'time_s': int(t_val),
                'time_h': round(t_val / 3600, 1),
                'pressures': {},
                'velocities': {},
            }

            # Node pressures
            for junc in self.wn.junction_name_list:
                step_data['pressures'][junc] = float(pressures_df.loc[t_val, junc])

            # Pipe velocities
            for pipe_name in self.wn.pipe_name_list:
                pipe = self.wn.get_link(pipe_name)
                area = math.pi * (pipe.diameter / 2) ** 2
                flow = float(flows_df.loc[t_val, pipe_name])
                step_data['velocities'][pipe_name] = abs(flow) / area if area > 0 else 0

            self.timesteps.append(step_data)

    @property
    def num_steps(self):
        return len(self.timesteps)

    @property
    def current_data(self):
        if 0 <= self.current_step < len(self.timesteps):
            return self.timesteps[self.current_step]
        return None

    @property
    def current_time_h(self):
        if self.current_data:
            return self.current_data['time_h']
        return 0

    def step_forward(self):
        if self.current_step < len(self.timesteps) - 1:
            self.current_step += 1
        return self.current_data

    def step_backward(self):
        if self.current_step > 0:
            self.current_step -= 1
        return self.current_data

    def go_to_step(self, step):
        self.current_step = max(0, min(step, len(self.timesteps) - 1))
        return self.current_data

    def reset(self):
        self.current_step = 0
        return self.current_data
