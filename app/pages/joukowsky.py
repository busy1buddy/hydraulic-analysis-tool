"""Joukowsky pressure rise calculator page."""

import plotly.graph_objects as go
from nicegui import ui
from app.theme import PLOTLY_LAYOUT, COLORS
from app.components.metrics import metric_card, update_metric


MATERIALS = {
    'Ductile Iron (~1000 m/s)': 1000,
    'Steel (~1100 m/s)': 1100,
    'PVC (~400 m/s)': 400,
    'PE/HDPE (~300 m/s)': 300,
    'Concrete (~1200 m/s)': 1200,
}


def create_page(api, status_refs):
    """Build the Joukowsky calculator page."""

    with ui.row().classes('w-full gap-4'):
        # Left: Calculator
        with ui.card().classes('flex-1'):
            ui.label('JOUKOWSKY PRESSURE RISE CALCULATOR').classes('section-title')
            ui.label('dH = (a x dV) / g').style(
                f'color: {COLORS["muted"]}; font-size: 13px; margin: 8px 0 16px 0; '
                f'font-style: italic')

            with ui.row().classes('gap-3 flex-wrap'):
                wave_input = ui.number('Wave Speed, a (m/s)', value=1000, min=100,
                                      step=50, format='%.0f').style('max-width: 180px')
                vel_input = ui.number('Velocity Change, dV (m/s)', value=1.0, min=0,
                                    step=0.1, format='%.2f').style('max-width: 180px')

                def on_material_change(e):
                    val = MATERIALS.get(e.value)
                    if val:
                        wave_input.value = val

                material_select = ui.select(
                    options=list(MATERIALS.keys()),
                    label='Pipe Material',
                    value='Ductile Iron (~1000 m/s)',
                    on_change=on_material_change,
                ).style('min-width: 200px')

            ui.button('Calculate', on_click=lambda: calculate()).props(
                'color=positive').style('margin-top: 12px')

            ui.separator().style(f'background: {COLORS["border"]}; margin-top: 16px')

            with ui.row().classes('w-full justify-around').style('margin-top: 12px'):
                head_label = metric_card('--', 'metres of head', 'Pressure Rise (dH)')
                pressure_label = metric_card('--', 'kPa', 'Pressure Rise (dP)')

        # Right: Wave speed reference chart
        with ui.card().classes('flex-1'):
            ui.label('WAVE SPEED REFERENCE (AUSTRALIAN PRACTICE)').classes('section-title')

            materials = ['PE/HDPE', 'PVC', 'Ductile Iron', 'Steel', 'Concrete']
            speeds = [300, 400, 1000, 1100, 1200]
            colors = [COLORS['green'], COLORS['accent'], COLORS['orange'],
                     COLORS['red'], '#8b5cf6']

            ref_fig = go.Figure()
            ref_fig.add_trace(go.Bar(
                x=speeds, y=materials, orientation='h',
                marker_color=colors,
                text=[f'{s} m/s' for s in speeds],
                textposition='outside',
                textfont=dict(color=COLORS['text'], size=12),
            ))
            layout = {**PLOTLY_LAYOUT}
            layout['xaxis'] = {**PLOTLY_LAYOUT['xaxis'], 'title': 'Wave Speed (m/s)',
                               'range': [0, 1500]}
            layout['margin'] = {'t': 10, 'r': 60, 'b': 40, 'l': 100}
            ref_fig.update_layout(**layout)

            ui.plotly(ref_fig).style('height: 380px')

    def calculate():
        result = api.joukowsky(
            wave_speed=float(wave_input.value),
            velocity_change=float(vel_input.value),
        )
        update_metric(head_label, str(result['head_rise_m']), COLORS['cyan'])
        update_metric(pressure_label, str(result['pressure_rise_kPa']), COLORS['cyan'])
