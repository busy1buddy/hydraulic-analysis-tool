"""Reusable Plotly network topology visualization component."""

import plotly.graph_objects as go
from app.theme import PLOTLY_LAYOUT, COLORS


def create_network_figure(wn):
    """Create a Plotly figure showing the network topology.

    Parameters
    ----------
    wn : wntr.network.WaterNetworkModel
        The loaded water network model.

    Returns
    -------
    go.Figure
    """
    fig = go.Figure()

    node_coords = {}
    for name in list(wn.junction_name_list) + list(wn.reservoir_name_list) + list(wn.tank_name_list):
        node = wn.get_node(name)
        node_coords[name] = node.coordinates

    # Draw pipes
    for pipe_name in wn.pipe_name_list:
        pipe = wn.get_link(pipe_name)
        sn, en = pipe.start_node_name, pipe.end_node_name
        if sn in node_coords and en in node_coords:
            x1, y1 = node_coords[sn]
            x2, y2 = node_coords[en]
            width = max(1.5, pipe.diameter * 1000 / 100)
            fig.add_trace(go.Scatter(
                x=[x1, x2], y=[y1, y2], mode='lines',
                line=dict(color=COLORS['accent'], width=width),
                hovertext=f'{pipe_name}: {sn}-{en} ({pipe.diameter*1000:.0f}mm)',
                hoverinfo='text', showlegend=False,
            ))

    # Draw valves
    for valve_name in wn.valve_name_list:
        valve = wn.get_link(valve_name)
        sn, en = valve.start_node_name, valve.end_node_name
        if sn in node_coords and en in node_coords:
            x1, y1 = node_coords[sn]
            x2, y2 = node_coords[en]
            fig.add_trace(go.Scatter(
                x=[x1, x2], y=[y1, y2], mode='lines',
                line=dict(color=COLORS['orange'], width=4, dash='dot'),
                hovertext=f'{valve_name} (Valve)',
                hoverinfo='text', showlegend=False,
            ))

    # Node types
    node_types = {
        'junction': {'names': list(wn.junction_name_list), 'color': COLORS['green'],
                     'symbol': 'circle', 'size': 10, 'label': 'Junction'},
        'reservoir': {'names': list(wn.reservoir_name_list), 'color': COLORS['accent'],
                      'symbol': 'square', 'size': 14, 'label': 'Reservoir'},
        'tank': {'names': list(wn.tank_name_list), 'color': COLORS['cyan'],
                 'symbol': 'diamond', 'size': 14, 'label': 'Tank'},
    }

    for ntype, cfg in node_types.items():
        if not cfg['names']:
            continue
        xs = [node_coords[n][0] for n in cfg['names'] if n in node_coords]
        ys = [node_coords[n][1] for n in cfg['names'] if n in node_coords]
        hover = []
        for n in cfg['names']:
            node = wn.get_node(n)
            txt = f'<b>{n}</b><br>Type: {ntype}'
            if hasattr(node, 'elevation'):
                txt += f'<br>Elev: {node.elevation}m'
            if hasattr(node, 'base_demand') and node.base_demand:
                txt += f'<br>Demand: {node.base_demand*1000:.1f} LPS'
            if hasattr(node, 'base_head'):
                txt += f'<br>Head: {node.base_head}m'
            hover.append(txt)

        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode='markers+text',
            marker=dict(color=cfg['color'], size=cfg['size'], symbol=cfg['symbol'],
                        line=dict(color='white', width=1)),
            text=[n for n in cfg['names'] if n in node_coords],
            textposition='top center', textfont=dict(size=9, color=COLORS['text']),
            hovertext=hover, hoverinfo='text', name=cfg['label'],
        ))

    layout = {**PLOTLY_LAYOUT}
    layout['xaxis'] = {**PLOTLY_LAYOUT['xaxis'], 'title': 'X (m)'}
    layout['yaxis'] = {**PLOTLY_LAYOUT['yaxis'], 'title': 'Y (m)', 'scaleanchor': 'x'}
    layout['showlegend'] = True
    layout['legend'] = {'bgcolor': 'rgba(0,0,0,0)', 'font': {'size': 10}, 'x': 0, 'y': 1}
    layout['margin'] = {'t': 10, 'r': 10, 'b': 40, 'l': 50}

    fig.update_layout(**layout)
    return fig
