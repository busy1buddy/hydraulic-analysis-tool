"""Compliance results display component."""

from nicegui import ui
from app.theme import COLORS


def render_compliance(container, compliance_list):
    """Render WSAA compliance results into a NiceGUI container.

    Parameters
    ----------
    container : ui element
        The NiceGUI container to render into.
    compliance_list : list of dict
        Each dict has 'type' (OK/WARNING/CRITICAL), 'message', optional 'element'.
    """
    container.clear()
    with container:
        if not compliance_list:
            ui.label('No compliance data').style('color: #8892a4; font-size: 13px')
            return

        for item in compliance_list:
            tag_type = item.get('type', 'OK')
            element = item.get('element', '')
            message = item.get('message', '')

            if tag_type == 'OK':
                color = COLORS['green']
                bg = '#065f46'
            elif tag_type == 'WARNING':
                color = '#fbbf24'
                bg = '#78350f'
            else:  # CRITICAL
                color = '#fca5a5'
                bg = '#7f1d1d'

            with ui.row().classes('items-center gap-2').style('margin-bottom: 4px'):
                ui.label(tag_type).style(
                    f'background: {bg}; color: {color}; padding: 1px 8px; '
                    f'border-radius: 3px; font-size: 10px; font-weight: 700'
                )
                text = f'{element} {message}' if element else message
                ui.label(text).style(f'color: {COLORS["text"]}; font-size: 12px')
