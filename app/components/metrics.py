"""Metric card display component."""

from nicegui import ui
from app.theme import COLORS


def metric_card(value='--', unit='', label='', color=None):
    """Create a metric display card.

    Returns the value label element so it can be updated later.
    """
    c = color or COLORS['accent']
    with ui.column().classes('items-center').style('padding: 8px; min-width: 100px'):
        val_label = ui.label(str(value)).style(
            f'font-size: 28px; font-weight: 700; color: {c}'
        )
        ui.label(unit).style(f'font-size: 12px; color: {COLORS["muted"]}')
        ui.label(label).style(f'font-size: 11px; color: {COLORS["muted"]}; margin-top: 2px')
    return val_label


def update_metric(label_element, value, color=None):
    """Update a metric label's value and optionally its color."""
    label_element.set_text(str(value))
    if color:
        label_element.style(f'font-size: 28px; font-weight: 700; color: {color}')
