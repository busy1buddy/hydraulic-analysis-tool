"""
3D Network Visualization Page (Enhanced)
==========================================
Interactive 3D view of the pipe network with:
- Orbit camera controls & view presets
- Color-coded results overlay (pressure, velocity, material)
- Animated flow particles showing direction & speed
- EPS result animation with play/pause/step/slider
- Selection highlighting with glow effect
- Measurement tool (click two points for distance)
- Toggleable labels (names, diameters, flows, pressures)
- Screenshot export
- Element property display panel
"""

from nicegui import ui
from app.theme import COLORS
from app.components.scene_3d import NetworkScene3D, EPSAnimator


def create_page(api, status_refs):
    """Build the 3D visualization page."""

    scene_ref = {'renderer': None}
    state = {
        'particle_data': None,
        'particle_timer': None,
        'animation_playing': False,
        'eps_animator': None,
        'eps_timer': None,
        'eps_playing': False,
        'measure_mode': False,
    }

    # ── Controls Row ──────────────────────────────────────────
    with ui.card().classes('w-full').style('margin-bottom: 16px'):
        ui.label('3D NETWORK VISUALIZATION').classes('section-title')

        # Row 1: Network selection and render
        with ui.row().classes('items-center gap-3 flex-wrap').style('margin-top: 8px'):
            network_select = ui.select(
                options=api.list_networks(), label='Network',
                value=api.list_networks()[0] if api.list_networks() else None,
            ).style('min-width: 200px')

            color_select = ui.select(
                options=['Default', 'Pressure', 'Velocity', 'Material'],
                label='Color By', value='Default',
            ).style('min-width: 150px')

            z_scale = ui.number('Vertical Scale', value=0.5, min=0.1,
                               max=5.0, step=0.1, format='%.1f').style('max-width: 140px')

            ui.button('Load & Render', on_click=lambda: render_network()).props(
                'color=primary icon=visibility')
            ui.button('Run Analysis + Color', on_click=lambda: run_and_color()).props(
                'color=positive icon=play_arrow')

        # Row 2: View presets + tools
        with ui.row().classes('gap-2 items-center flex-wrap').style('margin-top: 8px'):
            ui.label('Views:').style(f'color:{COLORS["muted"]};font-size:12px')
            ui.button('Plan', on_click=lambda: set_view('plan')).props('outline size=sm')
            ui.button('Isometric', on_click=lambda: set_view('iso')).props('outline size=sm')
            ui.button('Side', on_click=lambda: set_view('side')).props('outline size=sm')
            ui.button('Front', on_click=lambda: set_view('front')).props('outline size=sm')

            ui.separator().props('vertical').style('height:24px')

            ui.label('Tools:').style(f'color:{COLORS["muted"]};font-size:12px')
            measure_btn = ui.button('Measure', on_click=lambda: toggle_measure()).props(
                'outline size=sm icon=straighten')
            ui.button('Clear Measures', on_click=lambda: clear_measures()).props(
                'outline size=sm icon=delete_outline')
            ui.button('Screenshot', on_click=lambda: take_screenshot()).props(
                'outline size=sm icon=photo_camera')

        # Row 3: Label toggles
        with ui.row().classes('gap-2 items-center flex-wrap').style('margin-top: 8px'):
            ui.label('Labels:').style(f'color:{COLORS["muted"]};font-size:12px')
            lbl_names = ui.checkbox('Names', value=True,
                                   on_change=lambda e: toggle_label('names', e.value)).props('dense')
            lbl_diameters = ui.checkbox('Diameters', value=False,
                                       on_change=lambda e: toggle_label('diameters', e.value)).props('dense')
            lbl_flows = ui.checkbox('Flows', value=False,
                                   on_change=lambda e: toggle_label('flows', e.value)).props('dense')
            lbl_pressures = ui.checkbox('Pressures', value=False,
                                       on_change=lambda e: toggle_label('pressures', e.value)).props('dense')

    # ── Flow Animation Controls ───────────────────────────────
    with ui.card().classes('w-full').style('margin-bottom: 8px'):
        with ui.row().classes('items-center gap-3 flex-wrap'):
            ui.label('FLOW ANIMATION').classes('section-title')
            flow_play_btn = ui.button('Start Particles', on_click=lambda: toggle_particles()).props(
                'outline size=sm icon=animation color=cyan')
            flow_speed = ui.slider(min=0.01, max=0.2, step=0.01, value=0.05).style(
                'width: 120px').props('label')
            ui.label('Speed').style(f'color:{COLORS["muted"]};font-size:11px')
            particles_per_pipe = ui.number('Particles/Pipe', value=3, min=1, max=8,
                                          step=1).style('max-width: 130px')

    # ── EPS Animation Controls ────────────────────────────────
    with ui.card().classes('w-full').style('margin-bottom: 8px'):
        with ui.row().classes('items-center gap-3 flex-wrap'):
            ui.label('TIME ANIMATION').classes('section-title')
            eps_play_btn = ui.button('Play', on_click=lambda: toggle_eps()).props(
                'outline size=sm icon=play_arrow color=orange')
            ui.button('Step Back', on_click=lambda: eps_step(-1)).props(
                'outline size=sm icon=skip_previous')
            ui.button('Step Fwd', on_click=lambda: eps_step(1)).props(
                'outline size=sm icon=skip_next')
            ui.button('Reset', on_click=lambda: eps_reset()).props(
                'outline size=sm icon=replay')

            eps_color_select = ui.select(
                options=['Pressure', 'Velocity'],
                label='Animate By', value='Pressure',
            ).style('min-width: 130px')

        with ui.row().classes('items-center gap-3 w-full').style('margin-top: 4px'):
            eps_slider = ui.slider(min=0, max=1, step=1, value=0,
                                  on_change=lambda e: eps_go_to(int(e.value))).style(
                'flex: 1')
            eps_time_label = ui.label('T = 0.0 h').style(
                f'color:{COLORS["text"]};font-size:13px;min-width:100px')
            eps_step_label = ui.label('Step 0/0').style(
                f'color:{COLORS["muted"]};font-size:11px;min-width:80px')

    # ── Main content: 3D scene + info panel ───────────────────
    with ui.row().classes('w-full gap-4'):
        # 3D Scene + overlay legend
        with ui.card().style('flex: 3; position: relative'):
            # Floating color legend overlay (positioned over 3D scene)
            legend_overlay = ui.column().style(
                'position: absolute; top: 12px; right: 16px; z-index: 10; '
                'background: rgba(15, 20, 25, 0.88); border: 1px solid #2d3748; '
                'border-radius: 8px; padding: 10px 14px; min-width: 160px; '
                'pointer-events: none;'
            )
            with legend_overlay:
                legend_title = ui.label('').style(
                    'font-size: 11px; font-weight: 700; color: #8892a4; '
                    'text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;')
                legend_content = ui.column().style('gap: 3px; width: 100%')

            def update_legend(mode):
                """Update the floating legend based on active color mode."""
                legend_content.clear()

                if mode == 'pressure':
                    legend_title.set_text('Pressure (m)')
                    legend_overlay.set_visibility(True)
                    with legend_content:
                        # Gradient bar
                        ui.html(
                            '<div style="width:100%;height:14px;border-radius:3px;'
                            'background:linear-gradient(to right, '
                            '#ef4444 0%, #f97316 17%, #f59e0b 33%, '
                            '#10b981 50%, #06b6d4 67%, #3b82f6 100%);'
                            'margin-bottom:4px"></div>'
                        )
                        with ui.row().classes('w-full justify-between'):
                            ui.label('0').style('color:#ef4444;font-size:10px;font-weight:600')
                            ui.label('20').style('color:#f59e0b;font-size:10px;font-weight:600')
                            ui.label('40').style('color:#06b6d4;font-size:10px;font-weight:600')
                            ui.label('60+').style('color:#3b82f6;font-size:10px;font-weight:600')
                        ui.html('<div style="height:6px"></div>')
                        for val, label_text, color in [
                            ('< 10m', 'CRITICAL - Below minimum', '#ef4444'),
                            ('10-20m', 'LOW - Near WSAA limit', '#f97316'),
                            ('20-30m', 'ADEQUATE - WSAA compliant', '#f59e0b'),
                            ('30-40m', 'GOOD - Normal range', '#10b981'),
                            ('40-60m', 'HIGH - Monitor for surges', '#06b6d4'),
                            ('> 60m', 'VERY HIGH - Consider PRV', '#3b82f6'),
                        ]:
                            with ui.row().classes('items-center gap-2'):
                                ui.html(f'<div style="width:24px;height:10px;background:{color};'
                                        f'border-radius:2px;flex-shrink:0"></div>')
                                ui.label(val).style(f'color:{color};font-size:10px;'
                                                    f'font-weight:700;min-width:45px')
                                ui.label(label_text).style(
                                    f'color:{COLORS["muted"]};font-size:9px')
                        ui.html('<div style="height:4px"></div>')
                        ui.label('WSAA Min: 20m  |  Max: 50m').style(
                            f'color:{COLORS["orange"]};font-size:9px;font-weight:600')

                elif mode == 'velocity':
                    legend_title.set_text('Velocity (m/s)')
                    legend_overlay.set_visibility(True)
                    with legend_content:
                        ui.html(
                            '<div style="width:100%;height:14px;border-radius:3px;'
                            'background:linear-gradient(to right, '
                            '#3b82f6 0%, #06b6d4 25%, #10b981 50%, '
                            '#f59e0b 75%, #ef4444 100%);'
                            'margin-bottom:4px"></div>'
                        )
                        with ui.row().classes('w-full justify-between'):
                            ui.label('0').style('color:#3b82f6;font-size:10px;font-weight:600')
                            ui.label('1.0').style('color:#10b981;font-size:10px;font-weight:600')
                            ui.label('2.0+').style('color:#ef4444;font-size:10px;font-weight:600')
                        ui.html('<div style="height:6px"></div>')
                        for val, label_text, color in [
                            ('< 0.5', 'LOW - Possible sediment', '#3b82f6'),
                            ('0.5-1.0', 'MODERATE - Acceptable', '#06b6d4'),
                            ('1.0-1.5', 'GOOD - Optimal range', '#10b981'),
                            ('1.5-2.0', 'HIGH - Near limit', '#f59e0b'),
                            ('> 2.0', 'EXCEEDS - WSAA limit', '#ef4444'),
                        ]:
                            with ui.row().classes('items-center gap-2'):
                                ui.html(f'<div style="width:24px;height:10px;background:{color};'
                                        f'border-radius:2px;flex-shrink:0"></div>')
                                ui.label(val).style(f'color:{color};font-size:10px;'
                                                    f'font-weight:700;min-width:45px')
                                ui.label(label_text).style(
                                    f'color:{COLORS["muted"]};font-size:9px')
                        ui.html('<div style="height:4px"></div>')
                        ui.label('WSAA Max: 2.0 m/s').style(
                            f'color:{COLORS["orange"]};font-size:9px;font-weight:600')

                elif mode == 'material':
                    legend_title.set_text('Pipe Material')
                    legend_overlay.set_visibility(True)
                    with legend_content:
                        for mat_name, color in [
                            ('PVC (C > 140)', '#4488ff'),
                            ('PE / HDPE (C 120-140)', '#1a1a2e'),
                            ('Ductile Iron (C 100-120)', '#808080'),
                            ('Concrete (C 80-100)', '#b0a090'),
                            ('Steel (C 60-80)', '#707880'),
                            ('Cast Iron (C < 60)', '#555555'),
                        ]:
                            with ui.row().classes('items-center gap-2'):
                                ui.html(f'<div style="width:24px;height:10px;background:{color};'
                                        f'border-radius:2px;flex-shrink:0;'
                                        f'border:1px solid {COLORS["border"]}"></div>')
                                ui.label(mat_name).style(
                                    f'color:{COLORS["text"]};font-size:10px')
                        ui.html('<div style="height:4px"></div>')
                        ui.label('Detected from Hazen-Williams C').style(
                            f'color:{COLORS["muted"]};font-size:9px')

                else:
                    legend_title.set_text('')
                    legend_overlay.set_visibility(False)

            # Start hidden
            legend_overlay.set_visibility(False)

            scene_container = ui.column().style('width: 100%')

            def handle_scene_click(e):
                """Handle click on 3D scene element."""
                if not e.hits:
                    return

                hit = e.hits[0]

                # Measurement mode: use click coordinates
                if state['measure_mode'] and scene_ref.get('renderer'):
                    point = hit.point if hasattr(hit, 'point') else None
                    if point:
                        x = getattr(point, 'x', point.get('x', 0) if isinstance(point, dict) else 0)
                        y = getattr(point, 'y', point.get('y', 0) if isinstance(point, dict) else 0)
                        z = getattr(point, 'z', point.get('z', 0) if isinstance(point, dict) else 0)
                        result = scene_ref['renderer'].add_measurement_point(x, y, z)
                        if result:
                            measure_result.clear()
                            with measure_result:
                                ui.label(f"3D: {result['distance_3d']}m  |  "
                                         f"Horiz: {result['distance_horizontal']}m  |  "
                                         f"Vert: {result['distance_vertical']}m").style(
                                    f'color:{COLORS["cyan"]};font-size:12px')
                    return

                # Normal mode: select element
                obj_name = getattr(hit, 'object_name', None) or getattr(hit, 'name', None)
                if obj_name and api.wn:
                    # Highlight the clicked element
                    renderer = scene_ref.get('renderer')
                    if renderer:
                        renderer.highlight_element(obj_name)
                    show_element_info(obj_name)

            def build_scene():
                scene_container.clear()
                with scene_container:
                    scene = ui.scene(
                        width=900, height=550,
                        grid=(100, 20),
                        background_color='#0d1117',
                        on_click=handle_scene_click,
                    ).style('width: 100%')
                return scene

            scene = build_scene()

        # Properties panel (right side)
        with ui.card().style('flex: 1; min-width: 260px'):
            ui.label('ELEMENT INFO').classes('section-title')
            info_container = ui.column().style('width: 100%')
            with info_container:
                ui.label('Load a network and click an element').style(
                    f'color: {COLORS["muted"]}; font-size: 13px')

            ui.separator()

            # Measurement result area
            ui.label('MEASUREMENT').classes('section-title')
            measure_result = ui.column().style('width: 100%')
            with measure_result:
                ui.label('Use Measure tool + click two points').style(
                    f'color: {COLORS["muted"]}; font-size: 12px')

            ui.separator()

            ui.label('LEGEND').classes('section-title')
            with ui.column().style('gap: 4px'):
                for label_text, color, shape in [
                    ('Junction', COLORS['green'], 'border-radius:50%'),
                    ('Reservoir', COLORS['accent'], ''),
                    ('Tank', COLORS['cyan'], ''),
                    ('Pump', '#22c55e', ''),
                    ('Valve', COLORS['orange'], ''),
                ]:
                    with ui.row().classes('items-center gap-2'):
                        ui.html(f'<div style="width:12px;height:12px;background:{color};{shape}"></div>')
                        ui.label(label_text).style(f'color:{COLORS["text"]};font-size:12px')
                with ui.row().classes('items-center gap-2'):
                    ui.html('<div style="width:30px;height:6px;background:#4488cc;border-radius:3px"></div>')
                    ui.label('Pipe').style(f'color:{COLORS["text"]};font-size:12px')

            ui.separator()
            ui.label('PRESSURE SCALE').classes('section-title')
            with ui.column().style('gap: 2px'):
                for label_text, color in [('< 10m - Critical', '#ef4444'),
                                          ('10-20m - Low', '#f59e0b'),
                                          ('20-30m - Good', '#10b981'),
                                          ('30-40m - High', '#06b6d4'),
                                          ('> 40m - Very High', '#3b82f6')]:
                    with ui.row().classes('items-center gap-2'):
                        ui.html(f'<div style="width:20px;height:8px;background:{color};border-radius:2px"></div>')
                        ui.label(label_text).style(f'color:{COLORS["text"]};font-size:11px')

            ui.separator()
            ui.label('VELOCITY SCALE').classes('section-title')
            with ui.column().style('gap: 2px'):
                for label_text, color in [('< 0.5 m/s - Low', '#3b82f6'),
                                          ('0.5-1.0 m/s - Moderate', '#06b6d4'),
                                          ('1.0-1.5 m/s - Good', '#10b981'),
                                          ('1.5-2.0 m/s - High', '#f59e0b'),
                                          ('> 2.0 m/s - Exceeds', '#ef4444')]:
                    with ui.row().classes('items-center gap-2'):
                        ui.html(f'<div style="width:20px;height:8px;background:{color};border-radius:2px"></div>')
                        ui.label(label_text).style(f'color:{COLORS["text"]};font-size:11px')

            ui.separator()
            ui.label('MATERIAL COLORS').classes('section-title')
            with ui.column().style('gap: 2px'):
                for label_text, color in [('PVC', '#4488ff'), ('PE/HDPE', '#1a1a2e'),
                                          ('Ductile Iron', '#808080'), ('Steel', '#707880'),
                                          ('Concrete', '#b0a090'), ('Copper', '#b87333')]:
                    with ui.row().classes('items-center gap-2'):
                        ui.html(f'<div style="width:20px;height:8px;background:{color};border-radius:2px;'
                                f'border:1px solid {COLORS["border"]}"></div>')
                        ui.label(label_text).style(f'color:{COLORS["text"]};font-size:11px')

    # ── Action handlers ───────────────────────────────────────

    def render_network():
        nonlocal scene
        fname = network_select.value
        if not fname:
            ui.notify('Select a network', type='warning')
            return

        stop_all_animations()

        try:
            api.load_network(fname)
            status_refs['network'].set_text(fname)

            color_mode = color_select.value.lower()
            show_material = color_mode == 'material'
            if color_mode in ('default', 'material'):
                color_mode = None

            scene = build_scene()
            with scene:
                renderer = NetworkScene3D(
                    scene, api.wn,
                    scale_z=float(z_scale.value),
                    pipe_scale=0.3,
                )
                renderer.render_network(
                    color_by=color_mode,
                    show_material_colors=show_material,
                )
                renderer.center_camera()
                scene_ref['renderer'] = renderer

            update_legend(color_select.value.lower())
            ui.notify(f'Rendered {fname} in 3D', type='positive')
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    def run_and_color():
        nonlocal scene
        fname = network_select.value
        if not fname:
            return

        stop_all_animations()

        try:
            api.load_network(fname)
            results = api.run_steady_state(save_plot=False)

            color_mode = color_select.value.lower()
            show_material = color_mode == 'material'
            if color_mode in ('default', 'material'):
                color_mode = None

            scene = build_scene()
            with scene:
                renderer = NetworkScene3D(
                    scene, api.wn,
                    scale_z=float(z_scale.value),
                )
                renderer.render_network(
                    color_by=color_mode,
                    results=results,
                    show_material_colors=show_material,
                )
                renderer.center_camera()
                scene_ref['renderer'] = renderer

            # Set up EPS animator if results are available
            if hasattr(api, 'steady_results') and api.steady_results is not None:
                try:
                    animator = EPSAnimator(api.wn, api.steady_results)
                    state['eps_animator'] = animator
                    eps_slider.max = max(1, animator.num_steps - 1)
                    eps_slider.value = 0
                    eps_step_label.set_text(f'Step 0/{animator.num_steps - 1}')
                    eps_time_label.set_text(f'T = 0.0 h')
                except Exception:
                    state['eps_animator'] = None

            from datetime import datetime
            status_refs['last_analysis'].set_text(
                f'3D View @ {datetime.now().strftime("%I:%M:%S %p")}')

            update_legend(color_select.value.lower())
            ui.notify(f'3D view colored by {color_select.value}', type='positive')
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    # ── View presets ──────────────────────────────────────────

    def set_view(view_type):
        renderer = scene_ref.get('renderer')
        if not renderer or not renderer.coords:
            return

        coords = renderer.coords
        xs = [c[0] for c in coords.values()]
        ys = [c[1] for c in coords.values()]
        zs = [c[2] for c in coords.values()]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        cz = (min(zs) + max(zs)) / 2
        span = max(max(xs) - min(xs), max(ys) - min(ys), 20)

        if view_type == 'plan':
            scene.move_camera(x=cx, y=cz + span * 2, z=-cy,
                              look_at_x=cx, look_at_y=cz, look_at_z=-cy)
        elif view_type == 'iso':
            scene.move_camera(x=cx + span, y=cz + span, z=-cy + span,
                              look_at_x=cx, look_at_y=cz, look_at_z=-cy)
        elif view_type == 'side':
            scene.move_camera(x=cx + span * 2, y=cz, z=-cy,
                              look_at_x=cx, look_at_y=cz, look_at_z=-cy)
        elif view_type == 'front':
            scene.move_camera(x=cx, y=cz, z=-cy + span * 2,
                              look_at_x=cx, look_at_y=cz, look_at_z=-cy)

    # ── Flow particle animation ───────────────────────────────

    def toggle_particles():
        renderer = scene_ref.get('renderer')
        if not renderer:
            ui.notify('Render a network first', type='warning')
            return

        if state['animation_playing']:
            # Stop
            if state['particle_timer']:
                state['particle_timer'].cancel()
                state['particle_timer'] = None
            renderer.clear_particles()
            state['particle_data'] = None
            state['animation_playing'] = False
            flow_play_btn.text = 'Start Particles'
            flow_play_btn.props('icon=animation')
        else:
            # Start
            if not renderer.pipe_flow_data:
                ui.notify('Run analysis first to get flow data', type='warning')
                return

            n_pp = int(particles_per_pipe.value) if particles_per_pipe.value else 3
            pdata = renderer.create_particles(particles_per_pipe=n_pp)
            if not pdata:
                ui.notify('No flow in network - no particles to show', type='info')
                return

            state['particle_data'] = pdata
            state['animation_playing'] = True
            flow_play_btn.text = 'Stop Particles'
            flow_play_btn.props('icon=stop')

            def tick():
                if state['particle_data'] and state['animation_playing']:
                    renderer.animate_particles(state['particle_data'],
                                               dt=float(flow_speed.value))

            state['particle_timer'] = ui.timer(0.1, tick)

    # ── EPS time animation ────────────────────────────────────

    def toggle_eps():
        if state['eps_playing']:
            stop_eps()
        else:
            start_eps()

    def start_eps():
        animator = state.get('eps_animator')
        renderer = scene_ref.get('renderer')
        if not animator or not renderer:
            ui.notify('Run analysis first', type='warning')
            return

        state['eps_playing'] = True
        eps_play_btn.text = 'Pause'
        eps_play_btn.props('icon=pause')

        def eps_tick():
            if not state['eps_playing']:
                return
            anim = state['eps_animator']
            data = anim.step_forward()
            if data:
                color_mode = eps_color_select.value.lower()
                renderer.update_colors_for_timestep(data, color_by=color_mode)
                eps_slider.value = anim.current_step
                eps_time_label.set_text(f'T = {anim.current_time_h} h')
                eps_step_label.set_text(f'Step {anim.current_step}/{anim.num_steps - 1}')
            if anim.current_step >= anim.num_steps - 1:
                stop_eps()

        state['eps_timer'] = ui.timer(0.5, eps_tick)

    def stop_eps():
        state['eps_playing'] = False
        if state['eps_timer']:
            state['eps_timer'].cancel()
            state['eps_timer'] = None
        eps_play_btn.text = 'Play'
        eps_play_btn.props('icon=play_arrow')

    def eps_step(direction):
        animator = state.get('eps_animator')
        renderer = scene_ref.get('renderer')
        if not animator or not renderer:
            return
        if direction > 0:
            data = animator.step_forward()
        else:
            data = animator.step_backward()
        if data:
            color_mode = eps_color_select.value.lower()
            renderer.update_colors_for_timestep(data, color_by=color_mode)
            eps_slider.value = animator.current_step
            eps_time_label.set_text(f'T = {animator.current_time_h} h')
            eps_step_label.set_text(f'Step {animator.current_step}/{animator.num_steps - 1}')

    def eps_go_to(step):
        animator = state.get('eps_animator')
        renderer = scene_ref.get('renderer')
        if not animator or not renderer:
            return
        data = animator.go_to_step(step)
        if data:
            color_mode = eps_color_select.value.lower()
            renderer.update_colors_for_timestep(data, color_by=color_mode)
            eps_time_label.set_text(f'T = {animator.current_time_h} h')
            eps_step_label.set_text(f'Step {animator.current_step}/{animator.num_steps - 1}')

    def eps_reset():
        animator = state.get('eps_animator')
        renderer = scene_ref.get('renderer')
        if not animator or not renderer:
            return
        stop_eps()
        data = animator.reset()
        if data:
            color_mode = eps_color_select.value.lower()
            renderer.update_colors_for_timestep(data, color_by=color_mode)
            eps_slider.value = 0
            eps_time_label.set_text('T = 0.0 h')
            eps_step_label.set_text(f'Step 0/{animator.num_steps - 1}')

    def stop_all_animations():
        """Stop particles and EPS animation."""
        if state['particle_timer']:
            state['particle_timer'].cancel()
            state['particle_timer'] = None
        state['animation_playing'] = False
        state['particle_data'] = None
        flow_play_btn.text = 'Start Particles'
        flow_play_btn.props('icon=animation')
        stop_eps()
        state['eps_animator'] = None

    # ── Label toggles ─────────────────────────────────────────

    def toggle_label(category, visible):
        renderer = scene_ref.get('renderer')
        if renderer:
            renderer.set_labels_visible(category, visible)

    # ── Measurement tool ──────────────────────────────────────

    def toggle_measure():
        state['measure_mode'] = not state['measure_mode']
        if state['measure_mode']:
            measure_btn.props('color=cyan')
            ui.notify('Measure mode ON - click two points in 3D', type='info')
        else:
            measure_btn.props('color=primary outline')
            ui.notify('Measure mode OFF', type='info')

    def clear_measures():
        renderer = scene_ref.get('renderer')
        if renderer:
            renderer.clear_measurements()
        measure_result.clear()
        with measure_result:
            ui.label('Use Measure tool + click two points').style(
                f'color: {COLORS["muted"]}; font-size: 12px')

    # ── Screenshot ────────────────────────────────────────────

    def take_screenshot():
        js = """
        (() => {
            const canvases = document.querySelectorAll('canvas');
            if (canvases.length === 0) { return; }
            // Find the Three.js canvas (usually the largest one)
            let canvas = canvases[0];
            for (const c of canvases) {
                if (c.width * c.height > canvas.width * canvas.height) canvas = c;
            }
            // Force a render to ensure the canvas is up to date
            const url = canvas.toDataURL('image/png');
            const a = document.createElement('a');
            a.href = url;
            a.download = 'epanet_3d_view.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        })();
        """
        ui.run_javascript(js)
        ui.notify('Screenshot downloading...', type='positive')

    # ── Element info panel ────────────────────────────────────

    def show_element_info(obj_name):
        """Display element info in the properties panel."""
        if not obj_name or not api.wn:
            return

        info_container.clear()
        with info_container:
            if obj_name in api.wn.junction_name_list:
                node = api.wn.get_node(obj_name)
                ui.label(f'Junction: {obj_name}').style(
                    f'font-weight:700;color:{COLORS["text"]};font-size:14px')
                ui.label(f'Elevation: {node.elevation} m').style(
                    f'color:{COLORS["text"]};font-size:12px')
                demand = node.demand_timeseries_list[0].base_value * 1000 if node.demand_timeseries_list else 0
                ui.label(f'Demand: {demand:.1f} LPS').style(
                    f'color:{COLORS["text"]};font-size:12px')
                x, y = node.coordinates
                ui.label(f'Position: ({x:.1f}, {y:.1f})').style(
                    f'color:{COLORS["muted"]};font-size:11px')

                # Show analysis results if available
                renderer = scene_ref.get('renderer')
                if renderer and renderer.result_data and 'pressures' in renderer.result_data:
                    pdata = renderer.result_data['pressures'].get(obj_name)
                    if pdata:
                        ui.separator()
                        ui.label('Analysis Results').style(
                            f'font-weight:600;color:{COLORS["cyan"]};font-size:12px')
                        ui.label(f'Pressure: {pdata["min_m"]}-{pdata["max_m"]}m '
                                 f'(avg {pdata["avg_m"]}m)').style(
                            f'color:{COLORS["text"]};font-size:12px')

            elif obj_name in api.wn.reservoir_name_list:
                node = api.wn.get_node(obj_name)
                ui.label(f'Reservoir: {obj_name}').style(
                    f'font-weight:700;color:{COLORS["accent"]};font-size:14px')
                ui.label(f'Head: {node.base_head} m').style(
                    f'color:{COLORS["text"]};font-size:12px')

            elif obj_name in api.wn.tank_name_list:
                node = api.wn.get_node(obj_name)
                ui.label(f'Tank: {obj_name}').style(
                    f'font-weight:700;color:{COLORS["cyan"]};font-size:14px')
                ui.label(f'Elevation: {node.elevation} m').style(
                    f'color:{COLORS["text"]};font-size:12px')
                ui.label(f'Init Level: {node.init_level} m').style(
                    f'color:{COLORS["text"]};font-size:12px')
                ui.label(f'Max Level: {node.max_level} m').style(
                    f'color:{COLORS["text"]};font-size:12px')
                ui.label(f'Diameter: {node.diameter} m').style(
                    f'color:{COLORS["text"]};font-size:12px')

            elif obj_name in api.wn.pipe_name_list:
                pipe = api.wn.get_link(obj_name)
                from app.components.scene_3d import _detect_pipe_material
                material = _detect_pipe_material(pipe)
                ui.label(f'Pipe: {obj_name}').style(
                    f'font-weight:700;color:{COLORS["text"]};font-size:14px')
                ui.label(f'{pipe.start_node_name} -> {pipe.end_node_name}').style(
                    f'color:{COLORS["muted"]};font-size:12px')
                ui.label(f'Length: {pipe.length:.0f} m').style(
                    f'color:{COLORS["text"]};font-size:12px')
                ui.label(f'Diameter: {pipe.diameter*1000:.0f} mm').style(
                    f'color:{COLORS["text"]};font-size:12px')
                ui.label(f'Roughness: {pipe.roughness} (C)').style(
                    f'color:{COLORS["text"]};font-size:12px')
                ui.label(f'Material: {material.replace("_", " ").title()}').style(
                    f'color:{COLORS["orange"]};font-size:12px')

                # Show analysis results if available
                renderer = scene_ref.get('renderer')
                if renderer and renderer.result_data and 'flows' in renderer.result_data:
                    fdata = renderer.result_data['flows'].get(obj_name)
                    if fdata:
                        ui.separator()
                        ui.label('Analysis Results').style(
                            f'font-weight:600;color:{COLORS["cyan"]};font-size:12px')
                        ui.label(f'Flow: {fdata["avg_lps"]:.1f} L/s').style(
                            f'color:{COLORS["text"]};font-size:12px')
                        ui.label(f'Velocity: {fdata["avg_velocity_ms"]:.2f} m/s').style(
                            f'color:{COLORS["text"]};font-size:12px')

            elif obj_name in api.wn.pump_name_list:
                pump = api.wn.get_link(obj_name)
                ui.label(f'Pump: {obj_name}').style(
                    f'font-weight:700;color:#22c55e;font-size:14px')
                ui.label(f'{pump.start_node_name} -> {pump.end_node_name}').style(
                    f'color:{COLORS["muted"]};font-size:12px')

            elif obj_name in api.wn.valve_name_list:
                valve = api.wn.get_link(obj_name)
                ui.label(f'Valve: {obj_name}').style(
                    f'font-weight:700;color:{COLORS["orange"]};font-size:14px')
                ui.label(f'{valve.start_node_name} -> {valve.end_node_name}').style(
                    f'color:{COLORS["muted"]};font-size:12px')
                ui.label(f'Type: {valve.valve_type}').style(
                    f'color:{COLORS["text"]};font-size:12px')

            else:
                ui.label(f'Element: {obj_name}').style(
                    f'color:{COLORS["text"]};font-size:12px')
