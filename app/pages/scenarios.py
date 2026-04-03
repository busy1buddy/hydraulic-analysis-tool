"""Scenario comparison page for side-by-side what-if analysis."""

import sys
import os
import plotly.graph_objects as go
from nicegui import ui
from app.theme import PLOTLY_LAYOUT, COLORS, CHART_COLORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scenario_manager import ScenarioManager


def create_page(api, status_refs):
    """Build the scenario comparison page."""

    manager = ScenarioManager(api.work_dir)

    # --- Create scenario panel ---
    with ui.card().classes('w-full').style('margin-bottom: 16px'):
        ui.label('CREATE SCENARIO').classes('section-title')
        with ui.row().classes('items-center gap-3 flex-wrap').style('margin-top: 8px'):
            scenario_name = ui.input('Scenario Name', value='').style('max-width: 180px')
            base_network = ui.select(
                options=api.list_networks(), label='Base Network',
                value='australian_network.inp',
            ).style('min-width: 200px')
            scenario_desc = ui.input('Description', value='').style('min-width: 250px')

        ui.label('Modifications:').style(
            f'color: {COLORS["muted"]}; font-size: 12px; margin-top: 8px')

        with ui.row().classes('items-center gap-3 flex-wrap'):
            mod_type = ui.select(
                options=['pipe_diameter', 'pipe_roughness', 'demand_factor', 'demand_set'],
                label='Type', value='pipe_diameter',
            ).style('min-width: 160px')
            mod_target = ui.input('Target (Pipe/Junction ID)', value='P6').style('max-width: 160px')
            mod_value = ui.number('Value (mm/C-factor/multiplier)', value=250).style('max-width: 180px')

        modifications_list = []
        mods_display = ui.column()

        def add_modification():
            mod = {'type': mod_type.value, 'target': mod_target.value, 'value': float(mod_value.value)}
            if mod_type.value == 'demand_factor':
                mod.pop('target', None)
            modifications_list.append(mod)
            with mods_display:
                ui.label(f'  + {mod}').style(f'color: {COLORS["text"]}; font-size: 12px')

        with ui.row().classes('gap-2').style('margin-top: 8px'):
            ui.button('Add Modification', on_click=add_modification).props('outline')
            ui.button('Create Scenario', on_click=lambda: create_scenario()).props('color=primary')

    # --- Scenario list + comparison ---
    with ui.row().classes('w-full gap-4'):
        with ui.card().classes('flex-1'):
            ui.label('SCENARIOS').classes('section-title')
            scenario_list_container = ui.column().style('width: 100%')

        with ui.card().classes('flex-1'):
            ui.label('RUN & COMPARE').classes('section-title')
            with ui.row().classes('gap-3').style('margin-bottom: 8px'):
                compare_a = ui.input('Scenario A', value='').style('max-width: 150px')
                compare_b = ui.input('Scenario B', value='').style('max-width: 150px')
                ui.button('Compare', on_click=lambda: run_comparison()).props('color=warning')

            comparison_container = ui.column().style('width: 100%')

    # --- Comparison charts ---
    with ui.row().classes('w-full gap-4').style('margin-top: 16px'):
        with ui.card().classes('flex-1'):
            ui.label('PRESSURE COMPARISON').classes('section-title')
            pressure_compare_chart = ui.plotly({}).style('height: 350px')
        with ui.card().classes('flex-1'):
            ui.label('FLOW COMPARISON').classes('section-title')
            flow_compare_chart = ui.plotly({}).style('height: 350px')

    def create_scenario():
        name = scenario_name.value.strip()
        if not name:
            ui.notify('Enter a scenario name', type='warning')
            return

        mods = list(modifications_list)
        try:
            manager.create_scenario(name, base_network.value,
                                   modifications=mods,
                                   description=scenario_desc.value)
            modifications_list.clear()
            mods_display.clear()
            refresh_scenario_list()
            ui.notify(f'Scenario "{name}" created', type='positive')
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    def refresh_scenario_list():
        scenario_list_container.clear()
        with scenario_list_container:
            listing = manager.list_scenarios()
            if not listing:
                ui.label('No scenarios created yet').style(
                    f'color: {COLORS["muted"]}; font-size: 13px')
                return

            for s in listing:
                status = 'Results available' if s['has_results'] else 'Not yet run'
                color = COLORS['green'] if s['has_results'] else COLORS['muted']
                with ui.row().classes('items-center gap-2 w-full').style(
                    f'padding: 6px; border-left: 3px solid {color}; margin-bottom: 4px'):
                    ui.label(s['name']).style(
                        f'font-weight: 600; color: {COLORS["text"]}')
                    ui.label(f'({s["description"]})').style(
                        f'color: {COLORS["muted"]}; font-size: 12px')
                    ui.space()
                    ui.button('Run', on_click=lambda n=s['name']: run_scenario(n)).props(
                        'size=sm color=primary')

    def run_scenario(name):
        try:
            manager.run_scenario(name)
            refresh_scenario_list()
            ui.notify(f'Scenario "{name}" analysed', type='positive')
        except Exception as e:
            ui.notify(f'Error running {name}: {e}', type='negative')

    def run_comparison():
        a = compare_a.value.strip()
        b = compare_b.value.strip()
        if not a or not b:
            ui.notify('Enter both scenario names', type='warning')
            return

        result = manager.compare(a, b)
        if 'error' in result:
            ui.notify(result['error'], type='negative')
            return

        # Display comparison
        comparison_container.clear()
        with comparison_container:
            for s in result['summary']:
                ui.label(s).style(f'color: {COLORS["text"]}; font-size: 13px')

        # Pressure comparison chart
        junctions = list(result['pressure_diff'].keys())
        a_mins = [result['pressure_diff'][j]['a_min'] for j in junctions]
        b_mins = [result['pressure_diff'][j]['b_min'] for j in junctions]

        p_fig = go.Figure()
        p_fig.add_trace(go.Bar(x=junctions, y=a_mins, name=a,
                               marker_color=COLORS['accent']))
        p_fig.add_trace(go.Bar(x=junctions, y=b_mins, name=b,
                               marker_color=COLORS['orange']))
        p_fig.add_hline(y=20, line_dash='dash', line_color=COLORS['red'],
                       annotation_text='WSAA 20m')
        p_fig.update_layout(**PLOTLY_LAYOUT, barmode='group',
                           xaxis_title='Junction', yaxis_title='Min Pressure (m)',
                           showlegend=True)
        pressure_compare_chart.update_figure(p_fig)

        # Flow comparison chart
        pipes = list(result['flow_diff'].keys())
        a_flows = [result['flow_diff'][p]['a_avg'] for p in pipes]
        b_flows = [result['flow_diff'][p]['b_avg'] for p in pipes]

        f_fig = go.Figure()
        f_fig.add_trace(go.Bar(x=pipes, y=a_flows, name=a,
                               marker_color=COLORS['accent']))
        f_fig.add_trace(go.Bar(x=pipes, y=b_flows, name=b,
                               marker_color=COLORS['orange']))
        f_fig.update_layout(**PLOTLY_LAYOUT, barmode='group',
                           xaxis_title='Pipe', yaxis_title='Avg Flow (LPS)',
                           showlegend=True)
        flow_compare_chart.update_figure(f_fig)

        ui.notify('Comparison complete', type='positive')
