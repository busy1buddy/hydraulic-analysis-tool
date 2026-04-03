"""
EPANET Hydraulic Analysis Dashboard - NiceGUI Application
==========================================================
Main entry point for the NiceGUI-based dashboard.
Run with: python -m app.main
"""

import os
import sys

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nicegui import ui, app
from app.theme import COLORS, APP_CSS
from app.pages import steady_state, transient, joukowsky, feedback, scenarios, network_editor, view_3d

# Import the API
from epanet_api import HydraulicAPI

# Shared API instance
api = HydraulicAPI(work_dir=PROJECT_ROOT)

# Global CSS (shared=True applies to all pages)
ui.add_head_html(f'<style>{APP_CSS}</style>', shared=True)


@ui.page('/')
def main_page():
    # Dark mode
    ui.dark_mode().enable()
    ui.query('body').style(f'background-color: {COLORS["bg"]}')

    # --- Header ---
    with ui.header().style(
        f'background: linear-gradient(135deg, #1e3a5f 0%, {COLORS["bg"]} 100%); '
        f'border-bottom: 1px solid {COLORS["border"]}; padding: 12px 24px'
    ):
        with ui.row().classes('items-center gap-3 w-full'):
            ui.icon('water_drop').style(f'color: {COLORS["accent"]}; font-size: 24px')
            ui.label('EPANET Hydraulic Analysis').style(
                f'font-size: 18px; font-weight: 600; color: {COLORS["text"]}')

            ui.html('<span class="badge badge-blue">WNTR 1.4.0</span>')
            ui.html('<span class="badge badge-blue">TSNet MOC</span>')
            ui.html('<span class="badge badge-green">AU / SI Units</span>')

            ui.space()

            # Status indicators
            with ui.row().classes('items-center gap-4'):
                with ui.row().classes('items-center gap-1'):
                    ui.icon('circle').style(f'color: {COLORS["green"]}; font-size: 10px')
                    ui.label('Server:').style(f'color: {COLORS["muted"]}; font-size: 12px')
                    ui.label('Connected').style(f'color: {COLORS["text"]}; font-size: 12px')

                with ui.row().classes('items-center gap-1'):
                    ui.label('Network:').style(f'color: {COLORS["muted"]}; font-size: 12px')
                    network_status = ui.label('--').style(
                        f'color: {COLORS["text"]}; font-size: 12px')

                with ui.row().classes('items-center gap-1'):
                    ui.label('Last:').style(f'color: {COLORS["muted"]}; font-size: 12px')
                    last_analysis = ui.label('--').style(
                        f'color: {COLORS["text"]}; font-size: 12px')

    # Status refs for child pages to update
    status_refs = {
        'network': network_status,
        'last_analysis': last_analysis,
    }

    # --- Main content with tabs ---
    with ui.column().classes('w-full').style(
        f'max-width: 1400px; margin: 0 auto; padding: 16px'
    ):
        with ui.tabs().classes('w-full') as tabs:
            tab_steady = ui.tab('Steady-State Analysis').style(
                f'color: {COLORS["text"]}')
            tab_transient = ui.tab('Transient / Water Hammer').style(
                f'color: {COLORS["text"]}')
            tab_joukowsky = ui.tab('Joukowsky Calculator').style(
                f'color: {COLORS["text"]}')
            tab_3d = ui.tab('3D View').style(
                f'color: {COLORS["text"]}')
            tab_scenarios = ui.tab('Scenarios').style(
                f'color: {COLORS["text"]}')
            tab_editor = ui.tab('Network Editor').style(
                f'color: {COLORS["text"]}')
            tab_feedback = ui.tab('Feedback').style(
                f'color: {COLORS["text"]}')

        with ui.tab_panels(tabs, value=tab_steady).classes('w-full').style(
            'background: transparent'
        ):
            with ui.tab_panel(tab_steady):
                steady_state.create_page(api, status_refs)

            with ui.tab_panel(tab_transient):
                transient.create_page(api, status_refs)

            with ui.tab_panel(tab_joukowsky):
                joukowsky.create_page(api, status_refs)

            with ui.tab_panel(tab_3d):
                view_3d.create_page(api, status_refs)

            with ui.tab_panel(tab_scenarios):
                scenarios.create_page(api, status_refs)

            with ui.tab_panel(tab_editor):
                network_editor.create_page(api, status_refs)

            with ui.tab_panel(tab_feedback):
                feedback.create_page(api, status_refs)


def main():
    """Launch the NiceGUI application."""
    print(f'Starting EPANET Dashboard (NiceGUI) at http://localhost:8766')
    print(f'Working directory: {PROJECT_ROOT}')
    ui.run(
        title='EPANET Hydraulic Analysis',
        port=8766,
        dark=True,
        reload=False,
        show=False,
    )


if __name__ in {'__main__', '__mp_main__'}:
    main()
