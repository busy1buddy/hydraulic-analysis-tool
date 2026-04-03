"""Transient (water hammer) analysis page."""

import numpy as np
import plotly.graph_objects as go
from nicegui import ui
from app.theme import PLOTLY_LAYOUT, COLORS, CHART_COLORS
from app.components.compliance import render_compliance
from app.components.metrics import metric_card, update_metric


def create_page(api, status_refs):
    """Build the transient / water hammer analysis page."""

    # --- Controls ---
    with ui.card().classes('w-full').style('margin-bottom: 16px'):
        ui.label('TRANSIENT ANALYSIS PARAMETERS').classes('section-title')
        with ui.row().classes('items-center gap-3 flex-wrap').style('margin-top: 8px'):
            trans_network = ui.select(
                options=api.list_networks(), label='Network',
                value='transient_network.inp' if 'transient_network.inp' in api.list_networks() else None,
            ).style('min-width: 200px')
            valve_input = ui.input('Valve ID', value='V1').style('max-width: 100px')
            closure_input = ui.number('Closure Time (s)', value=0.5, min=0.01,
                                     step=0.1, format='%.2f').style('max-width: 140px')
            start_input = ui.number('Start Time (s)', value=2.0, min=0,
                                   step=0.5, format='%.1f').style('max-width: 130px')
            wave_input = ui.number('Wave Speed (m/s)', value=1000, min=100,
                                  step=50, format='%.0f').style('max-width: 150px')
            duration_input = ui.number('Duration (s)', value=20, min=5,
                                      step=5, format='%.0f').style('max-width: 120px')

        with ui.row().style('margin-top: 8px'):
            run_btn = ui.button('Run Water Hammer Analysis',
                               on_click=lambda: run_analysis()).props('color=warning')

    # --- Charts row 1: Head + Envelope ---
    with ui.row().classes('w-full gap-4'):
        with ui.card().classes('flex-1'):
            ui.label('TRANSIENT HEAD AT JUNCTIONS').classes('section-title')
            head_chart = ui.plotly({}).style('height: 350px')

        with ui.card().classes('flex-1'):
            ui.label('PRESSURE ENVELOPE').classes('section-title')
            envelope_chart = ui.plotly({}).style('height: 350px')

    # --- Results row: Compliance + Mitigation ---
    with ui.row().classes('w-full gap-4').style('margin-top: 16px'):
        with ui.card().classes('flex-1'):
            ui.label('TRANSIENT RESULTS').classes('section-title')
            trans_compliance = ui.column().style('max-height: 250px; overflow-y: auto')
            with trans_compliance:
                ui.label('Run analysis to see results').style(
                    f'color: {COLORS["muted"]}; font-size: 13px')

        with ui.card().classes('flex-1'):
            ui.label('MITIGATION RECOMMENDATIONS').classes('section-title')
            mitigation_container = ui.column()
            with mitigation_container:
                ui.label('Run analysis to see recommendations').style(
                    f'color: {COLORS["muted"]}; font-size: 13px')

            ui.separator().style(f'background: {COLORS["border"]}')
            with ui.row().classes('w-full justify-around'):
                surge_label = metric_card('--', 'm', 'Max Surge')
                surge_kpa_label = metric_card('--', 'kPa', 'Surge Pressure')
                rating_label = metric_card('PN35', '3500 kPa', 'Pipe Rating', COLORS['cyan'])

    # --- Run analysis ---
    async def run_analysis():
        fname = trans_network.value
        valve = valve_input.value
        if not fname or not valve:
            ui.notify('Select network and valve', type='warning')
            return

        run_btn.props('loading')
        try:
            api.load_network(fname)
            result = api.run_transient(
                valve_name=valve,
                closure_time=float(closure_input.value),
                start_time=float(start_input.value),
                wave_speed=float(wave_input.value),
                sim_duration=float(duration_input.value),
                save_plot=False,
            )

            # Head vs time chart
            tm = api.get_transient_model()
            t = tm.simulation_timestamps
            if isinstance(t, np.ndarray):
                t = t.tolist()

            h_fig = go.Figure()
            for i, node_name in enumerate(tm.junction_name_list):
                node = tm.get_node(node_name)
                h = node.head.tolist() if isinstance(node.head, np.ndarray) else node.head
                h_fig.add_trace(go.Scatter(
                    x=t, y=h, name=node_name,
                    line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=1.5),
                ))
            h_fig.add_vline(x=float(start_input.value), line_dash='dot',
                           line_color=COLORS['green'], annotation_text='Valve closure')
            h_fig.update_layout(**PLOTLY_LAYOUT, xaxis_title='Time (seconds)',
                               yaxis_title='Head (m)', showlegend=True)
            head_chart.update_figure(h_fig)

            # Pressure envelope
            junctions = list(result['junctions'].keys())
            steady_h = [result['junctions'][j]['steady_head_m'] for j in junctions]
            max_h = [result['junctions'][j]['max_head_m'] for j in junctions]
            min_h = [result['junctions'][j]['min_head_m'] for j in junctions]

            e_fig = go.Figure()
            e_fig.add_trace(go.Scatter(
                x=junctions, y=max_h, name='Max', mode='lines+markers',
                line=dict(color=COLORS['red']),
                marker=dict(symbol='triangle-up', size=8),
            ))
            e_fig.add_trace(go.Scatter(
                x=junctions, y=min_h, name='Min', mode='lines+markers',
                line=dict(color=COLORS['red']),
                marker=dict(symbol='triangle-down', size=8),
                fill='tonexty', fillcolor='rgba(239,68,68,0.15)',
            ))
            e_fig.add_trace(go.Scatter(
                x=junctions, y=steady_h, name='Steady', mode='lines+markers',
                line=dict(color=COLORS['accent'], width=2.5),
                marker=dict(size=8),
            ))
            e_fig.update_layout(**PLOTLY_LAYOUT, xaxis_title='Junction',
                               yaxis_title='Head (m)', showlegend=True)
            envelope_chart.update_figure(e_fig)

            # Transient results - per junction
            trans_compliance.clear()
            with trans_compliance:
                for name, d in result['junctions'].items():
                    surge = d['surge_m']
                    if surge > 30:
                        tag, bg, tc = 'HIGH', '#7f1d1d', '#fca5a5'
                    elif surge > 15:
                        tag, bg, tc = 'MOD', '#78350f', '#fbbf24'
                    else:
                        tag, bg, tc = 'OK', '#065f46', '#6ee7b7'
                    with ui.row().classes('items-center gap-2').style('margin-bottom: 4px'):
                        ui.label(tag).style(
                            f'background: {bg}; color: {tc}; padding: 1px 8px; '
                            f'border-radius: 3px; font-size: 10px; font-weight: 700')
                        ui.label(f'{name}: surge {surge}m ({d["surge_kPa"]} kPa), '
                                f'max {d["max_head_m"]}m').style(
                            f'color: {COLORS["text"]}; font-size: 12px')

            # Mitigation
            mitigation_container.clear()
            with mitigation_container:
                for m in result['mitigation']:
                    ui.label(f'  {m}').style(f'color: {COLORS["text"]}; font-size: 13px')

            # Metrics
            surge_m = result['max_surge_m']
            surge_color = COLORS['red'] if surge_m > 50 else (
                COLORS['orange'] if surge_m > 20 else COLORS['green'])
            update_metric(surge_label, str(surge_m), surge_color)
            update_metric(surge_kpa_label, str(result['max_surge_kPa']), surge_color)

            from datetime import datetime
            status_refs['last_analysis'].set_text(
                f'Transient @ {datetime.now().strftime("%I:%M:%S %p")}')

            ui.notify('Water hammer analysis complete', type='positive')

        except Exception as e:
            ui.notify(f'Analysis failed: {e}', type='negative')
        finally:
            run_btn.props(remove='loading')
