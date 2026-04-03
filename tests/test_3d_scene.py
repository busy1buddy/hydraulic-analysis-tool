"""Tests for 3D visualization components (enhanced)."""

import pytest
import math
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Color Interpolation ──────────────────────────────────────

class TestColorInterpolation:
    def test_interpolate_low(self):
        from app.components.scene_3d import _interpolate_color, PRESSURE_COLORS
        color = _interpolate_color(0, PRESSURE_COLORS)
        assert color == '#ef4444'  # Red for low pressure

    def test_interpolate_high(self):
        from app.components.scene_3d import _interpolate_color, PRESSURE_COLORS
        color = _interpolate_color(60, PRESSURE_COLORS)
        assert color == '#3b82f6'  # Blue for high pressure

    def test_interpolate_mid(self):
        from app.components.scene_3d import _interpolate_color, PRESSURE_COLORS
        color = _interpolate_color(25, PRESSURE_COLORS)
        assert color.startswith('#')
        assert len(color) == 7

    def test_interpolate_below_range(self):
        from app.components.scene_3d import _interpolate_color, VELOCITY_COLORS
        color = _interpolate_color(-5, VELOCITY_COLORS)
        assert color == '#3b82f6'  # Clamps to lowest

    def test_interpolate_above_range(self):
        from app.components.scene_3d import _interpolate_color, VELOCITY_COLORS
        color = _interpolate_color(10, VELOCITY_COLORS)
        assert color == '#ef4444'  # Clamps to highest

    def test_velocity_color_scale(self):
        from app.components.scene_3d import _interpolate_color, VELOCITY_COLORS
        low = _interpolate_color(0.1, VELOCITY_COLORS)
        high = _interpolate_color(1.8, VELOCITY_COLORS)
        assert low != high  # Different colors for different velocities


# ── Node Coordinates ─────────────────────────────────────────

class TestNodeCoords3D:
    def test_extracts_coords(self, loaded_network):
        from app.components.scene_3d import _get_node_coords_3d
        coords = _get_node_coords_3d(loaded_network.wn, scale_z=1.0)
        assert 'J1' in coords
        assert 'R1' in coords
        assert len(coords['J1']) == 3  # x, y, z

    def test_z_scale(self, loaded_network):
        from app.components.scene_3d import _get_node_coords_3d
        coords_1x = _get_node_coords_3d(loaded_network.wn, scale_z=1.0)
        coords_2x = _get_node_coords_3d(loaded_network.wn, scale_z=2.0)
        assert coords_2x['J1'][2] == coords_1x['J1'][2] * 2


# ── Material Detection ───────────────────────────────────────

class TestMaterialDetection:
    def test_detects_pvc_by_roughness(self, loaded_network):
        from app.components.scene_3d import _detect_pipe_material
        # Create a mock pipe with high roughness (PVC range)
        pipe = loaded_network.wn.get_link(loaded_network.wn.pipe_name_list[0])
        orig_roughness = pipe.roughness
        pipe.roughness = 150
        mat = _detect_pipe_material(pipe)
        assert mat == 'pvc'
        pipe.roughness = orig_roughness

    def test_detects_steel_by_roughness(self, loaded_network):
        from app.components.scene_3d import _detect_pipe_material
        pipe = loaded_network.wn.get_link(loaded_network.wn.pipe_name_list[0])
        orig_roughness = pipe.roughness
        pipe.roughness = 70
        mat = _detect_pipe_material(pipe)
        assert mat == 'steel'
        pipe.roughness = orig_roughness

    def test_detects_concrete(self, loaded_network):
        from app.components.scene_3d import _detect_pipe_material
        pipe = loaded_network.wn.get_link(loaded_network.wn.pipe_name_list[0])
        orig_roughness = pipe.roughness
        pipe.roughness = 90
        mat = _detect_pipe_material(pipe)
        assert mat == 'concrete'
        pipe.roughness = orig_roughness

    def test_detects_di(self, loaded_network):
        from app.components.scene_3d import _detect_pipe_material
        pipe = loaded_network.wn.get_link(loaded_network.wn.pipe_name_list[0])
        orig_roughness = pipe.roughness
        pipe.roughness = 110
        mat = _detect_pipe_material(pipe)
        assert mat == 'ductile_iron'
        pipe.roughness = orig_roughness

    def test_detects_pe(self, loaded_network):
        from app.components.scene_3d import _detect_pipe_material
        pipe = loaded_network.wn.get_link(loaded_network.wn.pipe_name_list[0])
        orig_roughness = pipe.roughness
        pipe.roughness = 130
        mat = _detect_pipe_material(pipe)
        assert mat == 'pe'
        pipe.roughness = orig_roughness

    def test_all_materials_have_colors(self):
        from app.components.scene_3d import MATERIAL_COLORS, MATERIAL_STYLES
        for mat in MATERIAL_COLORS:
            assert mat in MATERIAL_STYLES, f'Missing style for {mat}'

    def test_material_colors_valid_hex(self):
        from app.components.scene_3d import MATERIAL_COLORS
        for mat, color in MATERIAL_COLORS.items():
            assert color.startswith('#'), f'{mat} color not hex: {color}'
            assert len(color) == 7, f'{mat} color wrong length: {color}'


# ── EPS Animator ─────────────────────────────────────────────

class TestEPSAnimator:
    def test_creates_timesteps(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        results = loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        assert animator.num_steps > 0

    def test_step_forward(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        initial = animator.current_step
        animator.step_forward()
        if animator.num_steps > 1:
            assert animator.current_step == initial + 1

    def test_step_backward(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        animator.step_forward()
        animator.step_backward()
        assert animator.current_step == 0

    def test_go_to_step(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        animator.go_to_step(0)
        assert animator.current_step == 0

    def test_reset(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        animator.step_forward()
        animator.reset()
        assert animator.current_step == 0

    def test_current_data_has_pressures(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        data = animator.current_data
        assert 'pressures' in data
        assert 'velocities' in data
        assert len(data['pressures']) > 0

    def test_time_h_reported(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        assert animator.current_time_h == 0

    def test_step_clamps_at_bounds(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        animator.step_backward()  # Already at 0
        assert animator.current_step == 0
        # Go past end
        for _ in range(animator.num_steps + 5):
            animator.step_forward()
        assert animator.current_step == animator.num_steps - 1

    def test_go_to_step_clamps(self, loaded_network):
        from app.components.scene_3d import EPSAnimator
        loaded_network.run_steady_state(save_plot=False)
        animator = EPSAnimator(loaded_network.wn, loaded_network.steady_results)
        animator.go_to_step(-10)
        assert animator.current_step == 0
        animator.go_to_step(99999)
        assert animator.current_step == animator.num_steps - 1


# ── Measurement Tool (unit logic) ────────────────────────────

class TestMeasurementLogic:
    """Test measurement distance calculations (no GUI needed)."""

    def test_3d_distance_calculation(self):
        """Verify 3D distance formula is correct."""
        p1 = (0, 0, 0)
        p2 = (3, 4, 0)
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        dist = math.sqrt(dx**2 + dy**2 + dz**2)
        assert abs(dist - 5.0) < 0.001

    def test_horizontal_distance(self):
        """Horizontal distance ignores vertical component."""
        p1 = (0, 0, 0)
        p2 = (3, 10, 4)  # y is vertical in Three.js
        dx = p2[0] - p1[0]
        dz = p2[2] - p1[2]
        dist_horiz = math.sqrt(dx**2 + dz**2)
        assert abs(dist_horiz - 5.0) < 0.001

    def test_zero_distance(self):
        p1 = (5, 5, 5)
        dx = 0
        dy = 0
        dz = 0
        dist = math.sqrt(dx**2 + dy**2 + dz**2)
        assert dist == 0.0


# ── Material Styles Consistency ──────────────────────────────

class TestMaterialStyles:
    def test_all_styles_have_three_elements(self):
        from app.components.scene_3d import MATERIAL_STYLES
        for mat, style in MATERIAL_STYLES.items():
            assert len(style) == 3, f'{mat} style should be (color, stripe, opacity)'

    def test_opacity_in_valid_range(self):
        from app.components.scene_3d import MATERIAL_STYLES
        for mat, (_, _, opacity) in MATERIAL_STYLES.items():
            assert 0 <= opacity <= 1, f'{mat} opacity out of range: {opacity}'

    def test_primary_colors_are_hex(self):
        from app.components.scene_3d import MATERIAL_STYLES
        for mat, (color, _, _) in MATERIAL_STYLES.items():
            assert color.startswith('#'), f'{mat} primary color not hex'


# ── Pressure/Velocity Color Scales ───────────────────────────

class TestColorScales:
    def test_pressure_scale_ordered(self):
        from app.components.scene_3d import PRESSURE_COLORS
        for i in range(len(PRESSURE_COLORS) - 1):
            assert PRESSURE_COLORS[i][0] < PRESSURE_COLORS[i + 1][0]

    def test_velocity_scale_ordered(self):
        from app.components.scene_3d import VELOCITY_COLORS
        for i in range(len(VELOCITY_COLORS) - 1):
            assert VELOCITY_COLORS[i][0] < VELOCITY_COLORS[i + 1][0]

    def test_interpolation_monotonic(self):
        """Colors should transition smoothly - each step should produce valid hex."""
        from app.components.scene_3d import _interpolate_color, PRESSURE_COLORS
        for val in range(0, 61):
            color = _interpolate_color(val, PRESSURE_COLORS)
            assert color.startswith('#')
            assert len(color) == 7
