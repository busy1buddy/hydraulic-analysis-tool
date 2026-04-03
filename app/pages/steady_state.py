"""Steady-state hydraulic analysis page."""

import plotly.graph_objects as go
from nicegui import ui
from app.theme import PLOTLY_LAYOUT, COLORS, CHART_COLORS
from app.components.network_plot import create_network_figure
from app.components.compliance import render_compliance
from app.components.metrics import metric_card, update_metric


def create_page(api, status_refs):
    """Build the steady-state analysis page.

    Parameters
    ----------
    api : HydraulicAPI
        Shared API instance.
    status_refs : dict
        References to status bar labels for updating.
    """
    # --- State ---
    network_plot_ref = {'fig': None}
    pressure_plot_ref = {'fig': None}
    flow_plot_ref = {'fig': None}

    # --- Controls ---
    with ui.card().classes('w-full').style('margin-bottom: 16px'):
        with ui.row().classes('items-center gap-2'):
            ui.label('NETWORK SELECTION & ANALYSIS').classes('section-title')
        with ui.row().classes('items-center gap-3').style('margin-top: 8px'):
            network_select = ui.select(
                options=api.list_networks(),
                label='Network',
                value=api.list_networks()[0] if api.list_networks() else None,
            ).style('min-width: 250px')
            run_btn = ui.button('Run Steady-State Analysis',
                               on_click=lambda: run_analysis()).props('color=primary')

    # --- Charts row 1: Network + Compliance ---
    with ui.row().classes('w-full gap-4'):
        with ui.card().classes('flex-1'):
            ui.label('NETWORK TOPOLOGY').classes('section-title')
            network_chart = ui.plotly({}).style('height: 350px')

        with ui.card().classes('flex-1'):
            ui.label('AUSTRALIAN STANDARDS COMPLIANCE (WSAA)').classes('section-title')
            compliance_container = ui.column().style('max-height: 200px; overflow-y: auto')
            with compliance_container:
                ui.label('Run analysis to see compliance results').style(
                    f'color: {COLORS["muted"]}; font-size: 13px')

            ui.separator().style(f'background: {COLORS["border"]}')
            with ui.row().classes('w-full justify-around'):
                min_p_label = metric_card('--', 'm', 'Min Pressure')
                max_v_label = metric_card('--', 'm/s', 'Max Velocity')
                demand_label = metric_card('--', 'LPS', 'Total Demand')

    # --- Charts row 2: Pressures + Flows ---
    with ui.row().classes('w-full gap-4').style('margin-top: 16px'):
        with ui.card().classes('flex-1'):
            ui.label('JUNCTION PRESSURES (24HR)').classes('section-title')
            pressure_chart = ui.plotly({}).style('height: 320px')

        with ui.card().classes('flex-1'):
            ui.label('PIPE FLOWS (24HR)').classes('section-title')
            flow_chart = ui.plotly({}).style('height: 320px')

    # --- Load network on selection ---
    async def load_network():
        fname = network_select.value
        if not fname:
            return
        try:
            api.load_network(fname)
            status_refs['network'].set_text(fname)

            fig = create_network_figure(api.wn)
            network_chart.update_figure(fig)
        except Exception as e:
            ui.notify(f'Error loading network: {e}', type='negative')

    network_select.on_value_change(lambda _: load_network())

    # --- Run analysis ---
    async def run_analysis():
        fname = network_select.value
        if not fname:
            ui.notify('Select a network first', type='warning')
            return

        run_btn.props('loading')
        try:
            api.load_network(fname)
            results = api.run_steady_state(save_plot=False)

            # Update network plot
            fig = create_network_figure(api.wn)
            network_chart.update_figure(fig)

            # Update compliance
            render_compliance(compliance_container, results['compliance'])

            # Update metrics
            min_p = min(p['min_m'] for p in results['pressures'].values())
            max_v = max(f['max_velocity_ms'] for f in results['flows'].values())
            total_demand = sum(abs(f['avg_lps']) for f in results['flows'].values())

            update_metric(min_p_label, f'{min_p:.1f}',
                         COLORS['red'] if min_p < 20 else COLORS['green'])
            update_metric(max_v_label, f'{max_v:.2f}',
                         COLORS['red'] if max_v > 2.0 else COLORS['green'])
            update_metric(demand_label, f'{total_demand:.1f}', COLORS['accent'])

            # Pressure chart
            sr = api.steady_results
            pressures = sr.node['pressure']
            hours = (pressures.index / 3600).tolist()

            p_fig = go.Figure()
            for i, junc in enumerate(api.wn.junction_name_list):
                p_fig.add_trace(go.Scatter(
                    x=hours, y=pressures[junc].tolist(), name=junc,
                    line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
                ))
            p_fig.add_hline(y=20, line_dash='dash', line_color=COLORS['red'],
                           annotation_text='Min 20m (WSAA)')
            p_fig.update_layout(**PLOTLY_LAYOUT, xaxis_title='Time (hours)',
                               yaxis_title='Pressure (m)', showlegend=True)
            pressure_chart.update_figure(p_fig)

            # Flow chart
            flows = sr.link['flowrate']
            f_fig = go.Figure()
            for i, pipe_name in enumerate(api.wn.pipe_name_list):
                f_fig.add_trace(go.Scatter(
                    x=hours, y=(flows[pipe_name] * 1000).tolist(), name=pipe_name,
                    line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
                ))
            f_fig.update_layout(**PLOTLY_LAYOUT, xaxis_title='Time (hours)',
                               yaxis_title='Flow (LPS)', showlegend=True)
            flow_chart.update_figure(f_fig)

            # Update status
            from datetime import datetime
            status_refs['last_analysis'].set_text(
                f'Steady-State @ {datetime.now().strftime("%I:%M:%S %p")}')

            ui.notify('Steady-state analysis complete', type='positive')

        except Exception as e:
            ui.notify(f'Analysis failed: {e}', type='negative')
        finally:
            run_btn.props(remove='loading')

    # Auto-load first network
    if api.list_networks():
        ui.timer(0.5, lambda: load_network(), once=True)
